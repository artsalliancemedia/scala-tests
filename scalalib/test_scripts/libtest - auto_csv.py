import scalalib
import scalatools as st


if __name__ == '__ax_main__':  # scala

    svars = scalalib.sharedvars()
    st.auto_csv(svars.filename, 
        transforms={
            'event_name': lambda x: x.title(), 
            'group_name': lambda x: x.title(), 
            'start_time': st.convert_timestr,
            'end_time':   st.convert_timestr
            }, before=True, fields=(1,0) )

else:                           # command line
    log = scalalib.get_logger(level='debug', con=1, scala=0)

    st.auto_csv('test_scripts/schedule.csv', 
        transforms={
            'event_name': lambda x: x.title(), 
            'group_name': lambda x: x.title(), 
            'start_time': st.convert_timestr,
            'end_time':   st.convert_timestr
            })
