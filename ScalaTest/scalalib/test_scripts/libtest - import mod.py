import os
import scalalib
svars = scalalib.sharedvars()

os.chdir('test_scripts')

themod = scalalib.import_mod(svars.modulename)
reload(themod)
svars.results = str(themod)

