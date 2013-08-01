import scalalib as sl
svars = sl.sharedvars()

# now cached
print sl.get_metaval(svars.md_name)
print sl.get_metaval(svars.md_name)
print sl.get_metaval(svars.md_name)

svars.mdval = '> %s' % sl.get_metaval(svars.md_name)