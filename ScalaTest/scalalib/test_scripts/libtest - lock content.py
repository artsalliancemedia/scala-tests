import scalalib
svars = scalalib.sharedvars()

winpath = scalalib.lock_content(svars.file_to_install)

svars.results = '\n\nrealpath: ' + winpath

del winpath  # unlock
