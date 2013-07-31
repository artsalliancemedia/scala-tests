import sys, time
import scalalib as sl
import scalalink as sk
from msvcrt import getch

log = sl.get_logger(level='debug', con=1, scala=0)

# multicast udp, libtest.sca test
r = sk.MulticastUDPLink(port=21001).send('set foo="tudo bom?"')
if not r:  log.error('mismatch')
print

# remote serial
r = sk.SerialLink().send('ok remote serial test')
if not r == 'OK':  log.error('mismatch')
print

# remote tcp
r = sk.TCPLink(host='192.168.0.116').send('remote tcp test')
if not r == 'ERROR ValueError: unrecognized command passed.':  log.error('mismatch')
print

# # remote udp
r = sk.UDPLink(host='192.168.0.116', port=7600).send(
    'remote udp test\n after newline') # works
if not r:  log.error('mismatch')
print

# multicast udp
r = sk.MulticastUDPLink(port=5150).send('ok multicast-udp test')
if not r:  log.error('mismatch')
print

# localhost tcp
r = sk.TCPLink(port=5678, wrap=False).send(
    u'SCMD set myvar="Ivan Krsti\xc4\x87 ." \n')
if not r == 'SCMD ERROR NameError: variable myvar not found.\n':  log.error('mismatch')
print

# localhost udp
r = sk.UDPLink(host='localhost', port=6789).send('ok local "udp test')
if not r:  log.error('mismatch')
print

# localhost tcp unicode
tlink = sk.TCPLink(port=7800)
tlink.send('ok Ivan Krstic.')
print
tlink.send(u'ok Ivan "Krsti\xc4\x87 ." ')
print