"""
This is a simple client for the PVS XML-RPC connection

The basic idea is that your run PVS, which starts an XML-RPC server on some
port.  A client connects, sets up a server and sends its server port.

The idea is that there are two connections, to essentially implement
JSON-RPC, which has an implementation in Python, but does not seem to
in Lisp (though there is undocumented JSON-RPC in CL-JSON).

The advantage of using XML-RPC is that it is ubiquitous. 
"""

import json
import socket
import httplib
import exceptions
import xmlrpclib
import threading
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from urlparse import urlparse
import constants
import time
import util
import wx
import logging
import os.path
from wx.lib.pubsub import setupkwargs, pub

class PVSCommunicationLogger:
    __shared_state = {}
    
    def __init__(self):
        self.__dict__ = self.__shared_state
        if not "logName" in self.__dict__:
            self.logName = {}
            self.MAXNUMBEROFLOGS = 1000
            
    def createLogger(self, name):
        self.logName[name] = []

    def log(self, name, message):
        #message = "%d %s"%(time.time(), message)
        self.logName[name].append(str(message))
        pub.sendMessage(constants.PUB_APPENDLOG, name=name, message=message)
        if len(self.logName[name]) > self.MAXNUMBEROFLOGS:
            del self.logName[name][0]
        
    def clear(self, name):
        self.logName[name] = []
        
    def get(self, name):
        return self.logName[name]
    
    

# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

class PVSCommunicator:
    METHOD = "method"
    ID = "id"
    PARAMS = "params"
    REQUEST = "request"
    RESULT = "result"
    ERROR = "error"
    JSONRPC = "jsonrpc"
    JSONRPCRESULT = "jsonrpc_result"
    XMLRPCERROR = "xmlrpc_error"
    CONTEXT = "context"
    MODE = "mode"
    CODE = "code"
    MESSAGE = "message"
    DATA = "data"
    BEGIN = "begin"
    END = "end"
    THEORY = "theory"
    SILENT = "silent"
    
    
    __shared_state = {}
    
    def __init__(self, host=None, port=None):
        self.__dict__ = self.__shared_state
        # Create server
        if not "counter" in self.__dict__:
            logging.info("Initializing PVSCommunicator with (%s, %s)", host,port)
            self.counter = 0
            self.guiServer = None
            from config import PVSIDEConfiguration
            lg = PVSCommunicationLogger()
            lg.createLogger(constants.JSONLOG)
            lg.createLogger(constants.COMMENTARYLOG)
            cfg = PVSIDEConfiguration()
            self.ideURL = cfg.ideURL
            self.pvsURL = cfg.pvsURL
            jsonschemaFullname = os.path.join(cfg.applicationFolder, "src/pvs-gui.json")
            if os.path.exists(jsonschemaFullname):
                with open(jsonschemaFullname, 'r') as jsonschemaFile:
                    self.pvsJsonSchema = json.load(jsonschemaFile)
                    jsonschemaFile.close()
            self._doValidate = logging.getLogger(constants.LROOT).getEffectiveLevel() == logging.DEBUG
            
            
    def start(self):
        parsedURL = urlparse(self.ideURL)
        host = parsedURL.hostname
        port = parsedURL.port
        try:
            self.guiServer = SimpleXMLRPCServer((host, port), requestHandler=RequestHandler)
            self.guiServer.register_function(self.onPVSMessageReceived, PVSCommunicator.REQUEST)
            self.serverThread = threading.Thread(target=self.guiServer.serve_forever)
            self.serverThread.start()
            self.pvsProxy = xmlrpclib.ServerProxy(self.pvsURL)
        except Exception as e:
            logging.error("Error starting the xmlrpc server: %s", e)
            util.getMainFrame().showError("You may be running another instance of this application", "Error Starting the XMLRPC Server")
        
            
    def shutdown(self):
        if self.guiServer is not None:
            self.guiServer.shutdown()
        
    def _validateJSON(self, jsonObject):
        import jsonschema
        if self._doValidate:
            try:
                jsonschema.validate(jsonObject, self.pvsJsonSchema["definitions"])
                logging.debug("Validation successful for: %s", jsonObject)
            except Exception as err:
                logging.error("JSON Object is not valid: %s", err)
                raise err
            
    def requestPVS(self, method, *params):
        """ Send a request to PVS """
        reqid = 'gui_{0}'.format(self.counter)
        self.counter += 1
        request = {PVSCommunicator.METHOD: method, PVSCommunicator.PARAMS: params, PVSCommunicator.ID: reqid}
        self._validateJSON(request)
        jRequest = json.dumps(request)
        lg = PVSCommunicationLogger()
        lg.log(constants.JSONLOG, "=> %s\n"%(jRequest,))
        logging.debug("JSON request: %s", jRequest)
        sResult = self.pvsProxy.pvs.request(jRequest, self.ideURL)
        lg.log(constants.JSONLOG, "<= %s\n"%(sResult,))
        logging.debug("JSON result: %s", sResult)
        result = json.loads(sResult)
        self._validateJSON(result)
        return result
    
    def onPVSMessageReceived(self, jsonString):
        """
        Process a request from PVS
        
        An XML-RPC request presumably from PVS - typically a JSON-RPC
        message without id.  This always returns a value at the XML-RPC
        level.  If the JSON-RPC message cannot be parsed, or some other
        problem happens at the XML-RPC level, then it returns an error
        string.  If the JSON-RPC message is parsed, but doesn't include an
        id, then if an error occurs it is returned as a string.  If no id
        and no error, "null" is returned.  Otherwise, a valid JSON-RPC
        response/error form is returned.
        """
        logging.debug("Received: %s", jsonString)
        try:
            message = json.loads(jsonString)
            self._validateJSON(message)
            lg = PVSCommunicationLogger()
            lg.log(constants.JSONLOG, "<= %s\n"%(message,))
            result = self.processMessage(message)
            logging.debug("Sending Back: %s", result)
            self._validateJSON(result)
            lg.log(constants.JSONLOG, "=> %s\n"%(result,))
            return result
        #TODO: The return vlaues for errors should be different and json-based
        except TypeError as err:
            return 'request: {0} is of type {1}, string expected'.format(jsonString, type(jsonString))
        except ValueError as err:
            return 'request: {0} is invalid - {1}'.format(jsonString, err)
        except util.XMLRPCException as err:
            # Can't give normal JSON-RPC error response,
            # This is just an XML-RPC answer.
            return 'request: {0} is invalid - {1}'.format(jsonString, err)
        except Exception as err:
            return "Unknown Error"

    def processMessage(self, message):
        """
        Processes the json-rpc message
        """
        method = message[PVSCommunicator.METHOD]
        _id = message[PVSCommunicator.ID] if PVSCommunicator.ID in message else None
        params = message[PVSCommunicator.PARAMS] if PVSCommunicator.PARAMS in message else []
        result = PVSResponseManager().processCommand(_id, method, *params)
        return result

class PVSResponseManager:
    __shared_state = {}
    
    def __init__(self):
        self.__dict__ = self.__shared_state
                        
    def processCommand(self, _id, method, *parameters):
        functionName = "_process_" + method.replace("-", "_")
        if functionName in PVSResponseManager.__dict__:
            function = PVSResponseManager.__dict__[functionName]
            result = function(self, *parameters)
            sResult = self.resultToJSON(result, _id)
            return sResult
        else:
            self._process_everything_else(method, *parameters)
            
    def resultToJSON(self, result, _id):
        jResult = None
        if _id is not None:
            value = {}
            value[PVSCommunicator.ID] = _id
            value[PVSCommunicator.JSONRPC] = "2.0"
            value[PVSCommunicator.RESULT] = result
            jResult = {}
            jResult[PVSCommunicator.JSONRPCRESULT] = value
        jResultS = json.dumps(jResult)
        return jResultS
        
        
    def _process_yes_no(self, *parameters):
        logging.debug("PVS Info received. Parameters %s", (parameters,))
        frame = util.getMainFrame()
        question = parameters[0].strip()
        answer = frame.askYesNoQuestion(question)
        result = "yes" if answer==wx.ID_YES else "no"
        return result
        
    def _process_info(self, *parameters):
        logging.debug("PVS Info received. Parameters %s", (parameters,))

    def _process_debug(self, *parameters):
        logging.debug("PVS Debug received. Parameters %s", (parameters,))

    def _process_warning(self, *parameters):
        logging.debug("PVS Warning received. Parameters %s", (parameters,))
        
    def _process_buffer(self, *parameters):  
        logging.debug("buffer received. Parameters %s", (parameters,))

    def _process_everything_else(self, method, *parameters):
        logging.debug("Unknown method '%s' received. Parameters %s", method, (parameters,))
        raise util.PVSException("Unknown request method: %s"%method)
    
class PVSCommandManager:
    __shared_state = {}
    
    def __init__(self):
        self.__dict__ = self.__shared_state
        if not "pvsComm" in self.__dict__:
            self.pvsComm = PVSCommunicator()
            self.pvsComm.start()
            self.pvsMode = constants.PVS_MODE_UNKNOWN
            self.pvsContext = None
                        
    def _processJSONErrorObject(self, errDict):
            errorObject = {}
            errorObject[PVSCommunicator.CODE] = errDict[PVSCommunicator.CODE]
            errorObject[PVSCommunicator.MESSAGE] = errDict[PVSCommunicator.MESSAGE]
            if PVSCommunicator.DATA in errDict:
                data = errDict[PVSCommunicator.DATA]
                errorDataFile = data["error_file"]
                with open (errorDataFile, "r") as errorFile:
                    errorData = errorFile.read()
                errorFile.close()
                errorObject[PVSCommunicator.DATA] = errorData
                os.remove(errorDataFile)
                errorObject[PVSCommunicator.BEGIN] = data[PVSCommunicator.BEGIN]
                errorObject[PVSCommunicator.THEORY] = data[PVSCommunicator.THEORY]
                errorObject[PVSCommunicator.END] = data[PVSCommunicator.END] if PVSCommunicator.END in data else None
            else:
                logging.warning("error object %s did not have data", errDict)
                errorObject[PVSCommunicator.DATA] = ""
            return errorObject
            
    def _handleError(self, err):
        title = constants.ERROR
        if isinstance(err, socket.error):
            errMessage = err.strerror + "\nMake sure PVS is running and the port is set correctly"
            title = "PVS Communication Error"
        elif isinstance(err, httplib.BadStatusLine):
            errMessage = err.message
        elif isinstance(err, exceptions.ValueError):
            errMessage =  err.message
            title = "JSON Parse Error"
        elif isinstance(err, util.PVSException):
            data = err.errorObject[PVSCommunicator.DATA]
            if data is not None:
                title = err.message
                errMessage = err.errorObject[PVSCommunicator.DATA]
            else:
                errMessage = err.message
            if PVSCommunicator.BEGIN in err.errorObject:
                begin = err.errorObject[PVSCommunicator.BEGIN]
                end = err.errorObject[PVSCommunicator.END] if PVSCommunicator.END in err.errorObject else None
                pub.sendMessage(constants.PUB_ERRORLOCATION, begin=begin, end=end)
        elif isinstance(err, Exception):
            logging.debug("Unknown Exception: %s", err)
            errMessage = str(err)
        else:
            logging.debug("Unknown Thrown Object: %s", err)
            errMessage = str(err)
        logging.error("Error: %s", errMessage)
        util.getMainFrame().showError(errMessage, title)

    def _sendCommand(self, method, *params, **keywords):
        try:
            silent = keywords[PVSCommunicator.SILENT] if PVSCommunicator.SILENT in keywords else False
            jsonResult = self.pvsComm.requestPVS(method, *params)
            pvsMode = jsonResult[PVSCommunicator.MODE]
            context = util.normalizePath(jsonResult[PVSCommunicator.CONTEXT])
            if PVSCommunicator.XMLRPCERROR in jsonResult:
                errorObj = jsonResult[PVSCommunicator.XMLRPCERROR]
                errorObject = {}
                if isinstance(errorObj, str) or isinstance(errorObj, unicode):
                    logging.error("jsonResult[xmlrpc_error] should be a dictionary and not a string")
                    errorObject[PVSCommunicator.CODE] = -100
                    errorObject[PVSCommunicator.MESSAGE] = errorObj
                    errorObject[PVSCommunicator.DATA] = None
                else:
                    errorObject[PVSCommunicator.CODE] = int(errorObj[PVSCommunicator.CODE])
                    errorObject[PVSCommunicator.MESSAGE] = errorObj[PVSCommunicator.MESSAGE]
                    errorObject[PVSCommunicator.DATA] = errorObj[PVSCommunicator.DATA] if PVSCommunicator.DATA in errorObj else None
                raise util.PVSException(message=errorObject[PVSCommunicator.MESSAGE], errorObject=errorObject)
            result = jsonResult[PVSCommunicator.JSONRPCRESULT]
            if isinstance(result, str) or isinstance(result, unicode):
                result2 = json.loads(result)
                #TODO: Keep this for a while, but remove the if statement later if you never get an assertion error.
                #assert (result2 == result), "result '%s' is a json object inside a string"%result
                if result2 != result:
                    logging.error("result '%s' should not be a string here, but an object", result)
                    result2 = result
            if PVSCommunicator.ERROR in result:
                errDict = result[PVSCommunicator.ERROR]
                errorObject = self._processJSONErrorObject(errDict)
                raise util.PVSException(message=errorObject[PVSCommunicator.MESSAGE], errorObject=errorObject)
            result = result[PVSCommunicator.RESULT]
            if pvsMode != self.pvsMode:
                self.pvsMode = pvsMode
                pub.sendMessage(constants.PUB_UPDATEPVSMODE, pvsMode = pvsMode)   
            if context != self.pvsContext:
                self.pvsContext = context
                import preference
                preference.Preferences().setRecentContext(context)
                logging.debug("New Context is: %s", context)
                pub.sendMessage(constants.PUB_UPDATEPVSCONTEXT)
            return result
        except Exception as err:
            if not silent:
                self._handleError(err)
        return None
    
    def _ensureFilenameIsIknown(self, fullname):
        if fullname is None:
            fullname = util.getActiveFileName()
        if fullname is None:
            logging.warn("fullname is still None")
        return fullname
            
    def ping(self):
        result = self.lisp("(+ 1 2)", silent=True)
        if result != "3":
            pub.sendMessage(constants.PUB_UPDATEPVSMODE, pvsMode = constants.PVS_MODE_OFF)   
        return result
            
    def lisp(self, form, silent=False):
        result = self._sendCommand("lisp", form, silent=silent)
        return result
        
    def typecheck(self, fullname=None):
        fullname = self._ensureFilenameIsIknown(fullname)
        name = os.path.basename(fullname)
        name = util.getFilenameFromFullPath(fullname, False)
        pub.sendMessage(constants.PUB_REMOVEANNOTATIONS)
        result = self._sendCommand("typecheck", name)
        if result is not None:
            pub.sendMessage(constants.PUB_REMOVEANNOTATIONS)
            pub.sendMessage(constants.PUB_FILETYPECHECKED, fullname=fullname, result=result)
            self.namesInfo(fullname)
        return result
            
    def namesInfo(self, fullname=None):
        fullname = self._ensureFilenameIsIknown(fullname)
        name = os.path.basename(fullname)
        name = util.getFilenameFromFullPath(fullname, False)
        information = self._sendCommand("names-info", name)
        # {"id":"n","place":[27,36,27,37],"decl":"n: VAR nat","decl-file":"sum2.pvs","decl-place":[4,2,4,13]},
        if isinstance(information, str) or isinstance(information, unicode):
            logging.error("information '%s...' should not be a string. It should be a list", information[0:30])
            information = json.loads(information)
        information.sort(key=lambda x: x[constants.LPLACE])
        for inf in information:
            declFile = inf[constants.DECLFILE]
            if declFile is not None:
                if not os.path.isabs(declFile):
                    inf[constants.DECLFILE] = os.path.join(self.pvsContext, declFile)
            else:
                logging.warn("decl-file is None in %s", inf)
        pub.sendMessage(constants.PUB_NAMESINFOUPDATE, fullname=fullname, information=information)
        logging.debug("name-info returned: %s", information)
        return information
    
    def parse(self, fullname=None):
        fullname = self._ensureFilenameIsIknown(fullname)
        name = os.path.basename(fullname)
        name = os.path.splitext(name)[0] # just get the filename without the extension 
        pub.sendMessage(constants.PUB_REMOVEANNOTATIONS)
        result = self._sendCommand("parse", name)
        return result
    
    def changeContext(self, newContext):
        logging.debug("User requested to change context to: %s", newContext)
        result = self._sendCommand("change-context", newContext)
        if result is not None:
            result = util.normalizePath(result)
        return result
    
    def startProver(self, theoryName, formulaName):
        result = self._sendCommand("prove-formula", formulaName, theoryName)
        pub.sendMessage(constants.PUB_PROOFINFORMATIONRECEIVED, information=result) 
        return result
        
    def proofCommand(self, command):
        result = self._sendCommand("proof-command", command)
        assert result is not None
        pub.sendMessage(constants.PUB_PROOFINFORMATIONRECEIVED, information=result)
        return result
        
    
    
    

            