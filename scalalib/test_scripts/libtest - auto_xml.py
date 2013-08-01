import sys, string
sys.path.append(r'D:\src\projects\scalalib')

import scalalib
import scalatools as st
reload(st)
svars = scalalib.sharedvars()

if __name__ == '__ax_main__':  # scala

    def strip(value):
        return value.split('\n')[0]

    st.auto_xml(svars.filename, svars.roottag, transforms={'title':string.upper})
    # st.auto_xml(svars.filename, svars.roottag, 
        # transforms={'title': lambda x: x.split('\n')[0]} )

else:                           # command line

    log = scalalib.get_logger(level='info', con=1, scala=0)

    # st.auto_xml('rssdoc_short.xml', './/item')# , # 'channel'
    st.auto_xml('science_rss.xml', 'channel') #,
        # transforms={'height': int}, reverse=True,
        # fields=11) #('channel_item_content__height')        ) 
