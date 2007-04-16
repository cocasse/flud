"""
FludLocalClient.py, (c) 2003-2006 Alen Peacock.  This program is distributed
under the terms of the GNU General Public License (the GPL), version 2.

FludLocalClient provides a command-line client for interacting with FludNode.
"""
#!/usr/bin/python

import sys, os, time
from twisted.internet import reactor

from FludConfig import FludConfig
from fencode import *
from FludCrypto import *

from Protocol.LocalClient import *

# places where we are printing msgs to stdout need to instead put msgs in a
# buffer, to be printed when promptUser returns (i.e., down in the promptLoop()
# function).

def callFactory(func, commands, msgs):
	# since we can't call factory methods from the promptUser thread, we
	# use this as a convenience to put those calls back in the event loop
	reactor.callFromThread(doFactoryMethod, func, commands, msgs)

def doFactoryMethod(func, commands, msgs):
	d = func()
	d.addCallback(queueResult, msgs, '%s succeeded' % commands)
	d.addErrback(queueError, msgs, '%s failed' % commands)
	return d

def promptUser(factory):
	helpDict = {}

	command = raw_input("%s> " % time.ctime())
	commands = command.split(' ') # XXX: should tokenize on any whitespace
	commandkey = commands[0][:4]
	
	# core client operations
	helpDict['exit'] = "exit from the client"
	helpDict['help'] = "display this help message"
	helpDict['ping'] = "send a GETID() message: 'ping host port'"
	helpDict['putf'] = "store a file: 'putf canonicalfilepath'"
	helpDict['getf'] = "retrieve a file: 'getf canonicalfilepath'"
	helpDict['geti'] = "retrieve a file by CAS key: 'geti fencodedCASkey'"
	helpDict['fndn'] = "send a FINDNODE() message: 'fndn hexIDstring'"
	helpDict['list'] = "list stored files (read from local metadata)"
	helpDict['putm'] = "store master metadata"
	helpDict['getm'] = "retrieve master metadata"
	helpDict['cred'] = "send encrypted private credentials: cred"\
			" passphrase emailaddress"
	helpDict['node'] = "list known nodes"
	helpDict['buck'] = "print k buckets"
	helpDict['stat'] = "show pending actions"
	helpDict['stor'] = "store a block to a given node:"\
			" 'stor host:port,fname'"
	helpDict['rtrv'] = "retrieve a block from a given node:"\
			" 'rtrv host:port,fname'"
	helpDict['vrfy'] = "verify a block on a given node:"\
			" 'vrfy host:port:offset-length,fname'"
	helpDict['fndv'] = "retrieve a value from the DHT: 'fndv hexkey'"
	if commandkey == 'exit' or commandkey == 'quit':
		#reactor.callFromThread(reactor.stop)
		factory.quit = True
	elif commandkey == 'help':
		printHelp(helpDict)
	elif commandkey == 'ping':
		# ping a host
		# format: 'ping host port'
		func = lambda: factory.sendPING(commands[1], commands[2])
		callFactory(func, commands, factory.msgs)
	elif commandkey == 'putf':
		# store a file
		# format: 'putf canonicalfilepath'
		func = lambda: factory.sendPUTF(commands[1])
		callFactory(func, commands, factory.msgs)
	elif commandkey == 'getf':
		# retrieve a file
		# format: 'getf canonicalfilepath'
		func = lambda: factory.sendGETF(commands[1])
		callFactory(func, commands, factory.msgs)
	elif commandkey == 'geti':
		# retrieve a file by CAS ID
		# format: 'geti fencoded_CAS_ID'
		func = lambda: factory.sendGETI(commands[1])
		callFactory(func, commands, factory.msgs)
	elif commandkey == 'fndn':
		# find a node (or the k-closest nodes)
		# format: 'fndn hexIDstring'
		func = lambda: factory.sendFNDN(commands[1])
		callFactory(func, commands, factory.msgs)
	elif commandkey == 'list':
		# list stored files
		master = listMeta(factory.config)
		for i in master:
			if not isinstance(master[i], dict):
				print "%s: %s" % (i, fencode(master[i]))
	elif commandkey == 'putm':
		# store master metadata
		callFactory(factory.sendPUTM, commands, factory.msgs)
	elif commandkey == 'getm':
		# retrieve master metadata
		callFactory(factory.sendGETM, commands, factory.msgs)
	elif commandkey == 'cred':
		# send encrypted private credentials to an email address
		# format: 'cred passphrase emailaddress'
		func = lambda: factory.sendCRED(
				command[len(commands[0])+1:-len(commands[-1])-1], 
				commands[-1])
		callFactory(func, commands, factory.msgs)
		
	# the following are diagnostic operations, debug-only utility
	elif commandkey == 'node':
		# list known nodes
		callFactory(factory.sendDIAGNODE, commands, factory.msgs)
	elif commandkey == 'buck':
		# show k-buckets
		callFactory(factory.sendDIAGBKTS, commands, factory.msgs)
	elif commandkey == 'stat':
		# show pending actions
		print factory.pending
	elif commandkey == 'stor':
		# stor a block to a given node.  format: 'stor host:port,fname'
		storcommands = commands[1].split(',')
		try:
			fileid = int(storcommands[1], 16)
		except:
			linkfile = fencode(long(hashfile(storcommands[1]),16))
			if (os.path.islink(linkfile)):
				os.remove(linkfile)
			os.symlink(storcommands[1], linkfile)
			storcommands[1] = linkfile
			# XXX: delete this file when the command finishes
		commands[1] = "%s,%s" % (storcommands[0], storcommands[1])
		func = lambda: factory.sendDIAGSTOR(commands[1])
		callFactory(func, commands, factory.msgs)
	elif commandkey == 'rtrv':
		# retrive a block from a given node. format: 'rtrv host:port,fname'
		func = lambda: factory.sendDIAGRTRV(commands[1])
		callFactory(func, commands, factory.msgs)
	elif commandkey == 'vrfy':
		# verify a block on a given node.
		# format: 'vrfy host:port:offset-length,fname'
		func = lambda: factory.sendDIAGVRFY(commands[1])
		callFactory(func, commands, factory.msgs)
	elif commandkey == 'fndv':
		# try to retrieve a value from the DHT
		# format: 'fndv key'
		func = lambda: factory.sendDIAGFNDV(commands[1])
		callFactory(func, commands, factory.msgs)
	elif command != "":
		reactor.callFromThread(queueError, None, factory.msgs, 
				"illegal command '%s'" % command)


def queueResult(r, l, msg):
	l.append((r, msg))

def queueError(r, l, msg):
	l.append((None, msg))

def printHelp(helpDict):
	helpkeys = helpDict.keys()
	helpkeys.sort()
	for i in helpkeys:
		print "%s:\t %s" % (i, helpDict[i])

logger = logging.getLogger('flud')

def promptLoop(r, factory):
	for c in factory.pending:
		for i in factory.pending[c].keys():
			if factory.pending[c][i] == True:
				print "%s on %s completed successfully" % (c, i)
				factory.pending[c].pop(i)
			elif factory.pending[c][i] == False:
				print "%s on %s failed" % (c, i)
				factory.pending[c].pop(i)
			else:
				print "%s on %s pending" % (c, i)

	while len(factory.msgs) > 0:
		# this prints in reverse order, perhaps pop() all into a new list,
		# reverse, then print
		(r, m) = factory.msgs.pop()
		if r:
			print "<- %s:\n%s" % (m, r) 
		else:
			print "<- %s" % m

	if factory.quit:
		reactor.stop()
	else:
		d = threads.deferToThread(promptUser, factory)
		d.addCallback(promptLoopDelayed, factory)
		d.addErrback(err)

def promptLoopDelayed(r, factory):
	# give the reactor loop time to fire any quick cbs/ebs
	reactor.callLater(0.1, promptLoop, r, factory)

def err(r):
	print "bah!: %s" % r
	reactor.stop()

def main():
	config = FludConfig()
	config.load(doLogging=False)

	logger.setLevel(logging.DEBUG)
	handler = logging.FileHandler('/tmp/fludclient.log')
	formatter = logging.Formatter('%(asctime)s %(filename)s:%(lineno)d'
			' %(name)s %(levelname)s: %(message)s', datefmt='%H:%M:%S')
	handler.setFormatter(formatter)
	logger.addHandler(handler)

	factory = LocalClientFactory(config)
	factory.quit = False
	factory.msgs = []
	
	if len(sys.argv) == 2:
		config.clientport = int(sys.argv[1])
	
	print "connecting to localhost:%d" % config.clientport
	
	reactor.connectTCP('localhost', config.clientport, factory)
	
	promptLoop(None, factory)
	
	reactor.run()


if __name__ == '__main__':
	main()