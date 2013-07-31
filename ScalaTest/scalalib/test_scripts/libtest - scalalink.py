import sys
sys.path.append('.')
import scalalib as sl
from scalalink import *
log2 = sl.get_logger(level='debug')

tests = [False, False, False, False, False, False, False, False]

def scmd_foo(*args):
    return 'BAR ;)'

if tests[0]:
    s = SerialLink()
    s.listen() # serialargs=dict(baudrate=19200, parity='O', stopbits=2, bytesize=7) )
    print

if tests[1]:
    s = TCPLink(port=5678)
    s.send('ok')
    del s
    print

if tests[2]:
    s = UDPLink(host='192.168.0.116', port=7600)
    s.send('ok')
    del s
    print

if tests[3]:
    s = MulticastUDPLink(port=5150)
    s.send('ok')
    s._close()

if tests[4]:
    s = SerialLink().listen()
    print

if tests[5]:
    s = TCPLink(port=5000).listen(addhandlers=scmd_foo)
    print

if tests[6]:
    s = UDPLink(port=5001).listen()
    print

if tests[7]:
    s = MulticastUDPLink(port=5150).listen()
    print

