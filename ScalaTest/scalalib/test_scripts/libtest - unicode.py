import time
import scalalib as sl
log = sl.get_logger(level='debug')

import scalalink as sk

tlink = sk.TCPLink(port=7800)

tlink.send('ok Ivan Krstic.')
print
print
tlink.send(u'ok Ivan "Krsti\xc4\x87 ." ')
