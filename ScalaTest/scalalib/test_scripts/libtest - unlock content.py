import scalalib
svars = scalalib.sharedvars()

scalalib.unlock_content(svars.file_to_install)
svars.results = str(scalalib._locks)
