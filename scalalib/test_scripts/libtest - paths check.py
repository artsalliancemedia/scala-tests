import scalalib
import sys

svars = scalalib.sharedvars()

svars.realpath = scalalib.lock_content(svars.scalapath)

svars.scriptdir = scalalib.get_scriptdir()