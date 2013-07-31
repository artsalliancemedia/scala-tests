import sys, os
sys.path.insert(0, os.getcwdu())

import os
import scalalib
import scalatools as st

if __name__ == '__ax_main__':  # scala
    currdir = scalalib.get_scriptdir()
    svars = scalalib.sharedvars()
    query = svars.sql_query

else:                           # command line
    log = scalalib.get_logger(level='debug', con=1)
    currdir = os.path.join(os.getcwdu(), 'test_scripts')
    query = 'select * from table_page'

abspath = os.path.join(currdir, 'table.html')
constr  =  'Provider=Microsoft.Jet.OLEDB.4.0;'
constr += r'Data Source=%s;' % abspath
constr += r'Extended Properties="HTML Import;HDR=YES;IMEX=1";'

if __name__ == '__ax_main__':  # scala
    svars.sql_constr = constr  # return it


st.auto_sql(constr, query,
    transforms={
        u'item': lambda x: x.upper()
        })

