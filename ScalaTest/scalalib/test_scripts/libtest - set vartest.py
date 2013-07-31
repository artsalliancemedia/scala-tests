import scalalib as sl
import scalalink as sk

sk.MulticastUDPLink(port=port.Value, delay=0).listen()
