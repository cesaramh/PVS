;;; -*- Mode: Lisp; Package: SYNTAX-BOX -*-
(in-package "SYNTAX-BOX")  ;; creates package for abstract syntax. 

(in-package "SYNTAX-BOX")  ;; enters package for generated code.  

(use-package '("ERGOLISP" "OPER" "OCC" "TERM" "SORT" "SB-RUNTIME" "LANG" "NEWATTR"))


(export '())

(DEFPARAMETER SB-KEYWORD-LIST
              '(SBST::} SBST::{ SBST::|(| SBST::|,| SBST::|)| SBST::APPEND
               SBST::|(| SBST::|,| SBST::|)| SBST::BCONS SBST::|(| SBST::|,|
               SBST::|)| SBST::CONS SBST::|(| SBST::|,| SBST::|)| SBST::LIST
               SBST::|(| SBST::|,| SBST::|)| SBST::NULL SBST::@ SBST::SEQ
               SBST::DOUBLESTAR SBST::STAR SBST::DOUBLEPLUS SBST::PLUS
               SBST::ALT SBST::OPT SBST::* SBST::+ SBST::\| SBST::\| SBST::[
               SBST::] SBST::^ SBST::|::=| SBST::INITIAL SBST::MEDIAL
               SBST::LEFT SBST::RIGHT SBST::LBIND SBST::RBIND SBST::AGGREGATE
               SBST::BRACKETING SBST::OPERATORS SBST::COMMENT SBST::NEWLINE
               SBST::DELIMITED SBST::|;| SBST::SENSITIVE SBST::CASE
               SBST::GRAMMAR SBST::GRAMMARS SBST::EXTERNAL SBST::CHARACTER
               SBST::ESCAPE SBST::TERMINALS SBST::LEXICAL SBST::PRECEDENCE
               SBST::SPACING SBST::INFORMATION SBST::OP SBST::LT SBST::ARB
               SBST::OP SBST::LT SBST::ARB SBST::> SBST::|:| SBST::> SBST::<<
               SBST::> SBST::|:| SBST::> SBST::<< SBST::> SBST::< SBST::**
               SBST::++ SBST::JUXFORM SBST::JUX SBST::_ SBST::|#| SBST::/+
               SBST::/- SBST::? SBST::!+ SBST::!- SBST::@< SBST::@> SBST::@^)) 
(DEFPARAMETER SB-SINGLE-CHAR-OP-LIST
              '(#\? #\# #\_ #\^ #\| #\; #\, #\> #\} #\{ #\] #\[ #\) #\()) 
(DEFPARAMETER SB-MULTI-CHAR-OP-LIST
              '((#\< . LEX-<) (#\: . |LEX-:|) (#\+ . LEX-+) (#\* . LEX-*)
               (#\! . LEX-!) (#\/ . LEX-/) (#\@ . LEX-@))) 
(DEFPARAMETER SB-ALL-OPERATORS-LIST
              '(SBST::@^ SBST::@< SBST::@> SBST::/- SBST::/+ SBST::? SBST::|#|
               SBST::_ SBST::!+ SBST::!- SBST::** SBST::* SBST::++ SBST::+
               SBST::|::=| SBST::|:| SBST::@ SBST::^ SBST::\| SBST::|;|
               SBST::|,| SBST::<< SBST::> SBST::< SBST::} SBST::{ SBST::]
               SBST::[ SBST::|)| SBST::|(|)) 
(DEFPARAMETER SB-NEW-LINE-COMMENT-CHAR #\%) 
(DEFPARAMETER SB-OPEN-COMMENT-CHAR NIL) 
(DEFPARAMETER SB-CLOSE-COMMENT-CHAR NIL) 
(DEFPARAMETER SB-ESCAPE-CHAR #\\) 
(DEFPARAMETER SB-CASE-SENSITIVE NIL) 
(DEFPARAMETER SB-STRING-CHAR #\") 
(DEFPARAMETER SB-KEYWORD-CHAR #\') 
(DEFPARAMETER SB-LITERAL-CHAR #\`) 
(DEFPARAMETER SB-RESTRICTED-CHARS
              (REDUCE #'(LAMBDA (R
                                 S)
                          (UNION R S :TEST #'CHAR=))
                      (LIST SB-SINGLE-CHAR-OP-LIST
                            (IF SB-NEW-LINE-COMMENT-CHAR
                                (LIST SB-NEW-LINE-COMMENT-CHAR))
                            (IF SB-OPEN-COMMENT-CHAR
                                (LIST SB-OPEN-COMMENT-CHAR))
                            (IF SB-CLOSE-COMMENT-CHAR
                                (LIST SB-CLOSE-COMMENT-CHAR))
                            (IF SB-ESCAPE-CHAR (LIST SB-ESCAPE-CHAR))
                            (IF SB-STRING-CHAR (LIST SB-STRING-CHAR))
                            (IF SB-KEYWORD-CHAR (LIST SB-KEYWORD-CHAR))
                            (IF SB-LITERAL-CHAR (LIST SB-LITERAL-CHAR))))) 
(DEFVAR *SB-KEYWORD-TABLE* NIL) 
(DEFUN INIT-LEXER-AUX (LEXSTREAM)
  (INIT-LEXICAL-READTABLE LEXSTREAM :SINGLE-CHAR-OP-LIST SB-SINGLE-CHAR-OP-LIST
                          :NEW-LINE-COMMENT-CHAR SB-NEW-LINE-COMMENT-CHAR
                          :OPEN-COMMENT-CHAR SB-OPEN-COMMENT-CHAR :ESCAPE-CHAR
                          SB-ESCAPE-CHAR :MULTI-CHAR-OP-LIST
                          SB-MULTI-CHAR-OP-LIST)) 

(DEFUN INIT-LEXER (LEXSTREAM)
  (INIT-LEXER-AUX LEXSTREAM)
  (IF SB-STRING-CHAR
      (LEXICAL-MAKE-MACRO LEXSTREAM SB-STRING-CHAR #'READ-SB-STRING))
  (IF SB-KEYWORD-CHAR
      (LEXICAL-MAKE-MACRO LEXSTREAM SB-KEYWORD-CHAR #'READ-KEYWORD-STRING))
  (IF SB-LITERAL-CHAR
      (LEXICAL-MAKE-MACRO LEXSTREAM SB-LITERAL-CHAR #'READ-LITERAL))) 

(DEFUN LEX-@ (STREAM SYMBOL)
  (DECLARE (IGNORE SYMBOL))
  (LET (HOLDCHAR)
    (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF))
    (IF (AND SB-ESCAPE-CHAR (CHAR= HOLDCHAR SB-ESCAPE-CHAR))
        (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF)))
    (COND ((CHAR= HOLDCHAR #\^)
           'SBST::@^)
          ((CHAR= HOLDCHAR #\<)
           'SBST::@<)
          ((CHAR= HOLDCHAR #\>)
           'SBST::@>)
          (T
           (LEXICAL-UNREAD-CHAR STREAM)
           'SBST::@)))) 
(DEFUN LEX-/ (STREAM SYMBOL)
  (DECLARE (IGNORE SYMBOL))
  (LET (HOLDCHAR)
    (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF))
    (IF (AND SB-ESCAPE-CHAR (CHAR= HOLDCHAR SB-ESCAPE-CHAR))
        (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF)))
    (COND ((CHAR= HOLDCHAR #\-)
           'SBST::/-)
          ((CHAR= HOLDCHAR #\+)
           'SBST::/+)
          (T
           (LEXICAL-UNREAD-CHAR STREAM)
           (ILLEGAL-TOKEN-ERROR "/")
           :ILLEGAL-TOKEN)))) 
(DEFUN LEX-! (STREAM SYMBOL)
  (DECLARE (IGNORE SYMBOL))
  (LET (HOLDCHAR)
    (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF))
    (IF (AND SB-ESCAPE-CHAR (CHAR= HOLDCHAR SB-ESCAPE-CHAR))
        (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF)))
    (COND ((CHAR= HOLDCHAR #\+)
           'SBST::!+)
          ((CHAR= HOLDCHAR #\-)
           'SBST::!-)
          (T
           (LEXICAL-UNREAD-CHAR STREAM)
           (ILLEGAL-TOKEN-ERROR "!")
           :ILLEGAL-TOKEN)))) 
(DEFUN LEX-* (STREAM SYMBOL)
  (DECLARE (IGNORE SYMBOL))
  (LET (HOLDCHAR)
    (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF))
    (IF (AND SB-ESCAPE-CHAR (CHAR= HOLDCHAR SB-ESCAPE-CHAR))
        (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF)))
    (COND ((CHAR= HOLDCHAR #\*)
           'SBST::**)
          (T
           (LEXICAL-UNREAD-CHAR STREAM)
           'SBST::*)))) 
(DEFUN LEX-+ (STREAM SYMBOL)
  (DECLARE (IGNORE SYMBOL))
  (LET (HOLDCHAR)
    (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF))
    (IF (AND SB-ESCAPE-CHAR (CHAR= HOLDCHAR SB-ESCAPE-CHAR))
        (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF)))
    (COND ((CHAR= HOLDCHAR #\+)
           'SBST::++)
          (T
           (LEXICAL-UNREAD-CHAR STREAM)
           'SBST::+)))) 
(DEFUN |LEX-:| (STREAM SYMBOL)
  (DECLARE (IGNORE SYMBOL))
  (LET (HOLDCHAR)
    (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF))
    (IF (AND SB-ESCAPE-CHAR (CHAR= HOLDCHAR SB-ESCAPE-CHAR))
        (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF)))
    (COND ((CHAR= HOLDCHAR #\:)
           (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF))
           (IF (AND SB-ESCAPE-CHAR (CHAR= HOLDCHAR SB-ESCAPE-CHAR))
               (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF)))
           (COND ((CHAR= HOLDCHAR #\=)
                  'SBST::|::=|)
                 (T
                  (LEXICAL-UNREAD-CHAR STREAM)
                  (ILLEGAL-TOKEN-ERROR "::")
                  :ILLEGAL-TOKEN)))
          (T
           (LEXICAL-UNREAD-CHAR STREAM)
           'SBST::|:|)))) 
(DEFUN LEX-< (STREAM SYMBOL)
  (DECLARE (IGNORE SYMBOL))
  (LET (HOLDCHAR)
    (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF))
    (IF (AND SB-ESCAPE-CHAR (CHAR= HOLDCHAR SB-ESCAPE-CHAR))
        (SETF HOLDCHAR (LEXICAL-READ-CHAR STREAM :EOF)))
    (COND ((CHAR= HOLDCHAR #\<)
           'SBST::<<)
          (T
           (LEXICAL-UNREAD-CHAR STREAM)
           'SBST::<)))) 
