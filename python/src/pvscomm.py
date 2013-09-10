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
from preference import Preferences
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from urlparse import urlparse
import constants
import util
import logging
import os.path
from wx.lib.pubsub import setupkwargs, pub 

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
    
    
    __shared_state = {}
    
    def __init__(self, host=None, port=None):
        self.__dict__ = self.__shared_state
        # Create server
        if not "counter" in self.__dict__:
            logging.info("Initializing PVSCommunicator with (%s, %s)", host,port)
            self.counter = 0
            from config import PVSIDEConfiguration
            cfg = PVSIDEConfiguration()
            self.ideURL = cfg.ideURL
            parsedURL = urlparse(self.ideURL)
            host = parsedURL.hostname
            port = parsedURL.port
            self.guiServer = SimpleXMLRPCServer((host, port), requestHandler=RequestHandler)
            self.guiServer.register_function(self.onPVSMessageReceived, PVSCommunicator.REQUEST)
            self.serverThread = threading.Thread(target=self.guiServer.serve_forever)
            self.serverThread.start()
            self.pvsProxy = xmlrpclib.ServerProxy(cfg.pvsURL)
            
    def requestPVS(self, method, *params):
        """ Send a request to PVS """
        reqid = 'gui_{0}'.format(self.counter)
        self.counter += 1
        request = {PVSCommunicator.METHOD: method, PVSCommunicator.PARAMS: params, PVSCommunicator.ID: reqid}
        jRequest = json.dumps(request)
        logging.debug("JSON request: %s", jRequest)
        sResult = self.pvsProxy.pvs.request(jRequest, self.ideURL)
        logging.debug("JSON result: %s", sResult)
        result = json.loads(sResult)
        result = self.responseCheck(result)
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
            message = json.loads(jsonString, object_hook=self.requestCheck)
            result = self.processMessage(message)
            logging.debug("Sending Back: %s", result)
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

    def processMessage(self, message):
        """
        Processes the json-rpc message
        """
        method = message[PVSCommunicator.METHOD]
        _id = message[PVSCommunicator.ID] if PVSCommunicator.ID in message else None
        params = message[PVSCommunicator.PARAMS] if PVSCommunicator.PARAMS in message else []
        result = PVSResponseManager().processCommand(_id, method, *params)
        return result

    def responseCheck(self, dct):
        """
        Checks that the request is a JSON object (i.e., dictionary)
        with a method, jsonrpc of '2.0', optional id and params, and
        nothing else.
        """
        if not isinstance(dct, dict):
            raise util.XMLRPCException("Response '%s' must be a JSON object", dct)
        if not (PVSCommunicator.MODE in dct or PVSCommunicator.CONTEXT in dct):
            raise util.XMLRPCException("Response '%s' must include 'mode' and 'context'", dct)
        if PVSCommunicator.JSONRPCRESULT in dct:
            res = dct[PVSCommunicator.JSONRPCRESULT]
            if isinstance(res, str) or isinstance(res, unicode): #TODO: should not this be a json object already and not just a string?
                logging.warning("%s should already be a json object and not a string", res)
                res = json.loads(res)
            if not isinstance(res, dict):
                raise util.XMLRPCException("jsonrcp_result value '%s' must be a JSON object", res)
            if not PVSCommunicator.JSONRPC in res:
                logging.warning("%s does not have a jsonrpc key", res)
            if PVSCommunicator.ID in res:
                if not (PVSCommunicator.RESULT in res or PVSCommunicator.ERROR in res):
                    raise util.XMLRPCException("jsonrcp_result value '%s' must include either 'result' or 'error'", res)
        elif PVSCommunicator.XMLRPCERROR in dct:
            err = dct[PVSCommunicator.XMLRPCERROR]
            raise util.XMLRPCException("Error: " + str(err))
        return dct

    def requestCheck(self, dct):
        """
        Checks that the request is a JSON object (i.e., dictionary)
        with a method, jsonrpc of '2.0', optional id and params, and
        nothing else.
        """
        if not isinstance(dct, dict):
            raise util.XMLRPCException("Request must be a JSON object")
        if PVSCommunicator.JSONRPC not in dct:
            raise util.XMLRPCException("Request must include 'jsonrpcResult':")
        if PVSCommunicator.METHOD not in dct:
            raise util.XMLRPCException("Request must include a method")
        if not all(k in [PVSCommunicator.JSONRPC, PVSCommunicator.METHOD, PVSCommunicator.ID, PVSCommunicator.PARAMS] for k in dct.keys()):
            raise util.XMLRPCException("Request must only have 'jsonrpcResult', 'method', 'id', and 'params' fields")
        return dct


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
        return "yes" if answer==wx.ID_YES else "no"
    
        
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
            self.pvsMode = constants.PVS_MODE_UNKNOWN
            self.pvsContext = None
                        
    def sendRawCommand(self, command):
        logging.error("Unimplemented method")
        raise Exception("Unimplemented method: sendRawCommand")
    
    def _processError(self, err):
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
            errMessage = err.message
        elif isinstance(err, Exception):
            errMessage = err.message
        else:
            errMessage = str(err)
        logging.error("Error: %s", errMessage)
        util.getMainFrame().showError(errMessage, title)

    def _sendCommand(self, method, *params):
        try:
            jsonResult = self.pvsComm.requestPVS(method, *params)
            pvsMode = jsonResult[PVSCommunicator.MODE]
            context = util.normalizePath(jsonResult[PVSCommunicator.CONTEXT])
            if PVSCommunicator.XMLRPCERROR in jsonResult:
                errorObject = jsonResult[PVSCommunicator.XMLRPCERROR]
                code = int(errorObject[PVSCommunicator.CODE])
                message = errorObject[PVSCommunicator.MESSAGE]
                data = errorObject[PVSCommunicator.DATA] if PVSCommunicator.DATA in errorObject else None
                raise util.PVSException(message=message, code=code, data=data)
            result = jsonResult[PVSCommunicator.JSONRPCRESULT]
            if PVSCommunicator.ERROR in result:
                errDict = result[PVSCommunicator.ERROR]
                errorMessage = errDict["message"]
                errorCode = errDict["code"]
                errorDataFile = errDict["data"]["error_file"]
                with open (errorDataFile, "r") as errorFile:
                    errorData = errorFile.read()
                errorFile.close()
                #TODO delete the temp file.
                raise util.PVSException(message=errorMessage, code=errorCode, data=errorData)
            result = result[PVSCommunicator.RESULT]
            if pvsMode != self.pvsMode:
                self.pvsMode = pvsMode
                pub.sendMessage(constants.PUB_UPDATEPVSMODE, pvsMode = pvsMode)   
            if context != self.pvsContext:
                self.pvsContext = context
                Preferences().setRecentContext(context)
                logging.debug("New Context is: %s", context)
                pub.sendMessage(constants.PUB_UPDATEPVSCONTEXT)
            return result
        except Exception as err:
            self._processError(err)
        return None
            
    def ping(self):
        self._sendCommand("+", 1, 2)
            
    def typecheck(self, fullname):
        name = os.path.basename(fullname)
        name = util.getFilenameFromFullPath(fullname, False)
        result = self._sendCommand("typecheck", name)
        if result is not None:
            pub.sendMessage(constants.PUB_FILETYPECHECKED, fullname=fullname, result=result)
    
    def parse(self, fullname):
        name = os.path.basename(fullname)
        name = os.path.splitext(name)[0] # just get the filename without the extension 
        result = self._sendCommand("parse", name)
        return result
    
    def changeContext(self, newContext):
        logging.debug("User requested to change context to: %s", newContext)
        result = self._sendCommand("change-context", newContext)
        return result
    
    def startProver(self, theoryName, formulaName):
        result = self._sendCommand("prove-formula", formulaName, theoryName)
        pub.sendMessage(constants.PUB_PROOFINFORMATIONRECEIVED, information=result) 
        return result
        
    def proofCommand(self, command):
        result = self._sendCommand("proof-command", command)
        pub.sendMessage(constants.PUB_PROOFINFORMATIONRECEIVED, information=result)
        return result
        
    
    
    

            