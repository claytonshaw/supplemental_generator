import streamlit as st
import pandas as pd
import numpy as np
from Supplemental_Order import blank_rows, supplemental_order
import warnings
warnings.filterwarnings('ignore')

instructions = [
    'Step 1: Upload your files.',
    'Step 2: Set your parameters.',
    'Step 3: Click the "Generate" button.',
    'Step 4: View the results displayed below.',
    'Step 5: If satisfied download the "sto single" report.'
]

# main app function
def run():

    from PIL import Image
    logo = Image.open("blackstone-transparent.png")

    #st.image(image,use_column_width=False)

    st.sidebar.image(logo)

    st.sidebar.title('Instructions')
    for instrucion in instructions:
        st.sidebar.markdown(f"- {instrucion}")
    
    st.title("Supplemental Order Generator")

    st.header('File Upload')
    st.cache()
    data_upload = st.file_uploader("Upload Supplemental Data", type='xlsx')
    inventory_upload = st.file_uploader('Upload Inventory Data', type='xlsx')

    st.header('Parameters List')
    # list of parameters
    use_custom_vendor_packs = st.checkbox('Use Custom Vendor Packs (default is max shelf qty)') # switch this to False to use Max Shelf Qty as the cut off
    vendor_packs_to_send = st.number_input(label = 'Vendor Packs to Send', step=1) # number of vendor packs to send to stores
    use_available = st.checkbox('Use "Available - Split Pack" (Default is "On Hand")') # use either on hand or the available inventory (doesn't matter if you have just_find_need as "True")
    sort_by_zero_oh = st.checkbox('Sort by Zero On Hand at Stores (If not checked it will still sort by needed units)') # if true we will target stores that have zero on hand first
    just_find_need = st.checkbox('Just find Need (Makes BLKST on hand qty 1 million to find need at stores)') # makes the on hand qty 1 million so we can find the need and not be limited by what is on hand (switch to false to use either on hand or available)
    weeks_forecast = st.slider('Weeks Forecast', min_value=6, max_value=13, step=1)

    if st.button('Generate'):
        result_df, sto_single = supplemental_order(data_upload, inventory_upload, use_custom_vendor_packs, vendor_packs_to_send,
                    use_available, sort_by_zero_oh, just_find_need, weeks_forecast)

        def convert_df(df):
            return df.to_csv(index=False).encode('utf-8')
        csv = convert_df(sto_single)
        st.download_button('Download File as CSV', data = csv, file_name='sto_single.csv', mime='text/csv')

        st.write("The Results of the Supplemental Order:")
        st.write(result_df)

if __name__ == '__main__':
    run()
