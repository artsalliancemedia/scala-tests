import scalalib
import scalatools as st

svars = scalalib.sharedvars()

st.set_volume(svars.vol_val, svars.vol_comp, svars.vol_mute)


