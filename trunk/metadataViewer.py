#!/usr/bin/python
"""
metadataViewer.py (c) 2003-2006 Alen Peacock.  This program is distributed
under the terms of the GNU General Public License (the GPL).

utility for viewing metadata.
"""

from fencode import fencode, fdecode
from FludCrypto import FludRSA
import sys, os
import ConfigParser

if __name__ == "__main__":
	if len(sys.argv) < 2 or len(sys.argv) > 3:
		print "usage: %s [-r] <filename> " % sys.argv[0]
		print "       -r print as a raw dict"
		sys.exit()
	if len(sys.argv) == 3:
		fname = sys.argv[2]
		raw = True
	else:
		fname = sys.argv[1]
		raw = False
	
	try:
		# try to use Ku to decrypt metadata
		try:
			fludhome = os.environ['FLUDHOME']
		except:
			home = os.environ['HOME']
			fludhome = home+"/.flud"
		fludconfig = fludhome+"/flud.conf"
		c = ConfigParser.ConfigParser()
		if os.path.isfile(fludconfig) == True:
			conffile = file(fludconfig, "r")
			c.readfp(conffile)
		privkey = FludRSA.importPrivateKey( 
				eval(c.get("identification","Kr"))) 
	except:
		privkey = None

	f = os.open(fname, os.O_RDONLY)
	data = os.read(f,1280000)
	os.close(f)
	data = fdecode(data)
	if raw:
		print data
	else:
		for i in data:
			print "%s stored on:" % fencode(i)
			d = data[i]
			print "        %s" % fencode(d)
		print
		print "%d blocks" % len(data)

