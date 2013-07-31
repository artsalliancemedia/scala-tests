import scalalib as sl
import scalatools as st

if __name__ == '__ax_main__':  # scala

    log = sl.get_logger(  level='debug', svar='unpack_debug', scala=0,
        file=r"C:\Documents and Settings\mgmiller\Desktop\mike.log")
    svars = sl.sharedvars()
    st.unpack(svars.filename, overwrite=True)

else:                           # command line
    import sys
    log = sl.get_logger(level='debug', con=1, scala=0)
    st.unpack(sys.argv[1], dest='c:/mike')


