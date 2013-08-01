import scalalib as sl
import scalatools as st
svars = sl.sharedvars()

svars.mdval = '> %s' % st.get_metaval(svars.md_name)