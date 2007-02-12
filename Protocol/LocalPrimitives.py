"""
LocalPrimitives.py (c) 2003-2006 Alen Peacock.  This program is distributed
under the terms of the GNU General Public License (the GPL).

Protocol for talking to a flud node locally (from client code -- command line,
GUI, etc).
"""

from twisted.web.resource import Resource
from twisted.web import server, resource, client
from twisted.internet import protocol, reactor, threads, defer
from twisted.protocols import basic, smtp
from twisted.python import failure
from FludCrypto import FludRSA
from Crypto.Cipher import AES
import FludCrypto
import FludkRouting
import binascii, time, os, stat, httplib, gc, re, sys, logging, sets
from fencode import fencode, fdecode

from FludCommUtil import *
from FludServer import *
from FludFileOperations import *

logger = logging.getLogger("flud.local.server")

"""
Protocol and Factory for local client/server communication
"""

MAXCONCURRENT = 300
(CONCURR, MAX, QUEUE) = (0, 1, 2)  # indexes into LocalProtocol.commands

class LocalProtocol(basic.LineReceiver):
	authenticated = False
	commands = {'PUTF': [0, MAXCONCURRENT, []], 'GETF': [0, MAXCONCURRENT, []],
			'GETI': [0, MAXCONCURRENT, []], 'FNDN': [0, 1, []], 
			'STOR': [0, MAXCONCURRENT, []], 'RTRV': [0, MAXCONCURRENT, []], 
			'VRFY': [0, MAXCONCURRENT, []], 'FNDV': [0, 1, []], 
			'CRED': [0, 1, []], 'GETM': [0, 1, []], 'PUTM': [0, 1, []] }

	def connectionMade(self):
		logger.info("client connected")
		self.authenticated=False

	def connectionLost(self, reason):
		self.authenticated=False

	def doOp(self, command, fname):
		#print "got command '%s'" % command
		if command == "PUTF":
			logger.debug("PUTF");
			return StoreFile(self.factory.node, fname).deferred
		elif command == "GETI":
			logger.debug("GETI");
			return RetrieveFile(self.factory.node, fname).deferred
		elif command == "GETF":
			logger.debug("GETF");
			return RetrieveFilename(self.factory.node, fname).deferred
		elif command == "FNDN":
			logger.debug("FNDN %s" % fname);
			return self.factory.node.client.kFindNode(long(fname, 16))
			# The following is for testing aggregation of kFindNode on same key
			#dl = []
			#for i in [1,2,3,4,5]:
			#	d = self.factory.node.client.kFindNode(long(fname, 16))
			#	dl.append(d)
			#dlist = defer.DeferredList(dl)
			#return dlist
		elif command == "FNDV":
			logger.debug("FNDV %s" % fname);
			return self.factory.node.client.kFindValue(long(fname, 16))
		elif command == "CRED":
			passphrase, email = fdecode(fname)
			# XXX: allow an optional passphrase hint to be sent in email.
			passphrase = self.factory.node.config.Kr.decrypt(passphrase)
			logger.debug("CRED %s to %s" % (passphrase, email));
			Kr = self.factory.node.config.Kr.exportPrivateKey()
			Kr['g'] = self.factory.node.config.groupIDr
			fKr = fencode(Kr)
			key = AES.new(binascii.unhexlify(FludCrypto.hashstring(passphrase)))
			fKr = '\x00'*(16-(len(fKr)%16))+fKr
			efKr = fencode(key.encrypt(fKr))
			logger.debug("efKr = %s " % efKr)
			d = smtp.sendmail('localhost', "your_flud_client@localhost", 
					email,
					"Subject: Your encrypted flud credentials\n\n"
					"Hopefully, you'll never need to use this email.  Its "
					"sole purpose is to help you recover your data after a "
					"catastrophic and complete loss of the original computer "
					"or hard drive.\n\n"
					"In that unlucky event, you'll need a copy of your flud "
					"credentials, which I've included below, sitting between "
					"the \"---+++---\" markers.  These credentials were "
					"encrypted with a passphrase of your choosing when you "
					"installed the flud software.  I'll only say this "
					"once:\n\n"
					"YOU MUST REMEMBER THAT PASSWORD IN ORDER TO RECOVER YOUR "
					"CREDENTIALS.  If you are unable to remember the "
					"passphrase and your computer fails catastrophically "
					"(losing its local copy of these credentials), you will "
					"not be able to recover your data."
					"\n\n"
					"Luckily, that's all you should ever need in order to "
					"recover all your data: your passphrase and these "
					"credentials."
					"\n\n"
					"Please save this email.  You may want to print out hard "
					"copies and store them safely, forward this email to "
					"other email accounts, etc.  Since the credentials are "
					"encrypted, others won't be able to steal them "
					"without guessing your passphrase. "
					"\n\n"
					"---+++---\n"+efKr+"\n---+++---\n")
			return d
			# to decode this email, we search for the '---+++---' markers, make
			# sure the intervening data is all in one piece (remove any line
			# breaks \r or \n inserted by email clients) and call this 'cred',
			# reconstruct the AES key with the H(passphrase) (as above), and
			# then use the key to .decrypt(fdecode(cred)) and call this dcred,
			# then fdecode(dcred[dcred.find('d'):]) and call this ddcred, and
			# finally importPrivateKey(ddcred) and set groupIDr to ddcred['g'].
		elif command == "GETM":
			logger.debug("GETM");
			return RetrieveMasterIndex(self.factory.node).deferred
		elif command == "PUTM":
			logger.debug("PUTM");
			return UpdateMasterIndex(self.factory.node).deferred
		else:
			#print "fname is '%s'" % fname
			host = fname[:fname.find(':')]
			port = fname[fname.find(':')+1:fname.find(',')]
			fname = fname[fname.find(',')+1:]
			print "%s: %s : %s , %s" % (command, host, port, fname)
			if command == "STOR":
				logger.debug("STOR");
				return self.factory.node.client.sendStore(fname, host, 
						int(port))
			elif command == "RTRV":
				logger.debug("RTRV");
				return self.factory.node.client.sendRetrieve(fname, host, 
						int(port))
			elif command == "VRFY":
				logger.debug("VRFY");
				offset = port[port.find(':')+1:port.find('-')]
				length = port[port.find('-')+1:]
				port = port[:port.find(':')]
				print "%s: %s : %s %s - %s , %s" % (command, host, port, 
						offset, length, fname)
				return self.factory.node.client.sendVerify(fname, int(offset), 
						int(length), host, int(port))
			else:
				logger.debug("bad op");
				return defer.fail("bad op")

	def serviceQueue(self, command):
		if len(self.commands[command][QUEUE]) > 0 and \
				self.commands[command][CONCURR] <= self.commands[command][MAX]:
			data = self.commands[command][QUEUE].pop()
			logger.info("servicing queue['%s'], item %s" % (command, data))
			print "taking %s off the queue" % command
			d = self.doOp(command, data)
			d.addCallback(self.sendSuccess, command, data)
			d.addErrback(self.sendFailure, command, data)
	
	def sendSuccess(self, resp, command, data, prepend=None):
		print "SUCCESS! "+command+":"+data #+" ("+str(resp)+")"
		if prepend:
			data = command+" "+data
			ncommand = prepend
		else:
			ncommand = command
		self.transport.write(ncommand+":"+data+"\r\n")
		self.commands[command][CONCURR] -= 1
		try:
			self.serviceQueue(command)
		except:
			print sys.exec_info()

	def sendFailure(self, err, command, data, prepend=None):
		print "FAILED! "+command+"!"+data +" ("+err.getErrorMessage()+")" 
		if prepend:
			data = command+" "+data
			ncommand = prepend
		else:
			ncommand = command
		self.transport.write(ncommand+"!"+data+"\r\n")
		self.commands[command][CONCURR] -= 1
		self.serviceQueue(command)

	def lineReceived(self, line):
		# commands: AUTH, PUTF, GETF, VRFY
		# status: ? = request, : = successful response, ! = failed response
		command = line[0:4]
		status = line[4]
		data = line[5:]
		#print "data is '%s'" % data
		if not self.authenticated and command == "AUTH":
			if status == '?':
				# asked for AUTH challenge to be sent.  send it
				echallenge = self.factory.sendChallenge()
				self.transport.write("AUTH?"+echallenge+"\r\n")
			elif status == ':' and self.factory.challengeAnswered(data):
				# sent AUTH response and it passed
				self.authenticated = True
				self.transport.write("AUTH:\r\n")
			elif status == ':':
				self.transport.write("AUTH!\r\n")
		elif command == "DIAG":
			if data == "NODE":
				self.transport.write("DIAG:NODE"+
						str(self.factory.config.routing.knownExternalNodes())+
						"\r\n")
			elif data == "BKTS":
				self.transport.write("DIAG:BKTS"+
						str(self.factory.config.routing.kBuckets)+
						"\r\n")
			else:
				dcommand = data[:4]
				ddata = data[5:]
				self.commands[dcommand][CONCURR] += 1
				d = self.doOp(dcommand, ddata)
				d.addCallback(self.sendSuccess, dcommand, ddata, "DIAG")
				d.addErrback(self.sendFailure, dcommand, ddata, "DIAG")
		elif status == '?':
			# requested an operation to be performed.  If we are below our
			# maximum concurrent ops, do the operation.  Otherwise, put it on
			# the queue to be serviced when current ops finish.  Response is
			# sent back to client when deferreds fire.
			logger.info("local client sent %s" % command)
			if self.commands[command][CONCURR] >= self.commands[command][MAX]:
				#print "putting %s on the queue" % line
				self.commands[command][QUEUE].insert(0, data)
			else:
				#print "doing %s" % line
				print self.commands[command]
				self.commands[command][CONCURR] += 1
				d = self.doOp(command, data)
				d.addCallback(self.sendSuccess, command, data)
				d.addErrback(self.sendFailure, command, data)

class LocalFactory(protocol.ServerFactory):
	protocol = LocalProtocol
	
	def __init__(self, node):
		self.node = node
		self.config = node.config

	def sendChallenge(self):
		self.challenge = fencode(FludCrypto.generateRandom(challengelength))
		echallenge = self.config.Ku.encrypt(self.challenge)[0]
		echallenge = fencode(echallenge)
		return echallenge

	def challengeAnswered(self, resp):
		return resp == self.challenge
