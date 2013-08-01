import scalalib
import scalatools as st
svars = scalalib.sharedvars()

result = st.msgbox('check defaults')
svars.results = str(result)

result = st.msgbox('stop test', title='stop title', icon='stop',
    buttons='abort_retry_ignore', timeout=5)
svars.results = str(result)
    
result = st.msgbox('question???????', title='question title', 
    icon='question', buttons='yes_no', timeout=30)
svars.results = str(result)


