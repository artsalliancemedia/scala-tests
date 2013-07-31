import scalalib
import scalatools as st
svars = scalalib.sharedvars()

svars.results = str( st.get_ini(svars.filepath, svars.ini_section) )

