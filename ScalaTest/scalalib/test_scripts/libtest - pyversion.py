import sys
import scalalib
import scalatools as st
import scalalink as sk

# makes sure we are using the newest module, otherwise would have to restart
reload(scalalib)  
reload(st)
reload(sk)

pyversion.value = sys.version
scalalib_ver.value = scalalib.__version__