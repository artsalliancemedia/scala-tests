import sys
sys.path.append('..')
import scalalink as sk
import scalalib as sl
log = sl.get_logger(level='debug')

test = sys.argv[1]


if test == 'net.tcp':
    sk.TCPLink(host='').listen()

if test == 'net.udp.7600':
    sk.UDPLink(port=7600, host='').listen()
    
if test == 'net.multicast.udp.5150':
    sk.MulticastUDPLink(port=5150).listen()

if test == 'serial.port.0':
    sk.SerialLink().listen()

if test == 'bad.transport':
    pass # sk.TCPLink()listen()

if test == 'local.tcp.5678':
    sk.TCPLink(host='localhost', port=5678).listen()

if test == 'local.udp.6789':
    sk.UDPLink(host='localhost', port=6789).listen()

if test == 'local.tcp.7900.tokill':
    sk.TCPLink(port=7900).listen()

if test == 'local.tcp.7800.unicode':
    sk.TCPLink(port=7800, uniparse=True).listen()


