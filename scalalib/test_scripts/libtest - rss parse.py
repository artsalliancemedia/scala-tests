import scalalib
import scalatools as st
svars = scalalib.sharedvars()

if __name__ == '__ax_main__':  # scala

    channel = st.DataChain(svars.filename, svars.roottag)
    svars.rss_title = channel.title
    svars.rss_lang  = channel.language
    svars.rss_item_titles = [ item.title.split('\n')[0]  
                                for item in channel.items ]
    
else:                           # command line

    # test normally
    channel = st.DataChain('science_rss.xml', roottag='channel')

    # test with file object
    # fobj = file("C:\Documents and Settings\mgmiller\Local Settings\Temp\science_rss.xml")
    # channel = scalalib.DataChain(fobj, roottag='channel')

    print 'desc:', channel.description
    print 'image:', channel.image
    print 'image.height', channel.image.height
    # print 'item titles:', [ item.title for item in channel.items ]
    print 'item titles:', [ item.title  for item in channel.items ]

