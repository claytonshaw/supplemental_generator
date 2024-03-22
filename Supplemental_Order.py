# function that will dynamically count the number of blank rows
def blank_rows(file_path):
    import pandas as pd
    # Read the first column of the Excel sheet to find blank rows
    first_column = pd.read_excel(file_path, usecols=[0]).iloc[:, 0]

    # Find the number of consecutive blank rows at the beginning
    blank_rows = 1
    for value in first_column:
        if pd.isnull(value):
            blank_rows += 1
        else:
            break
    return blank_rows


def supplemental_order(file_upload,inventory_upload,use_custom_vendor_packs=False, vendor_packs_to_send=0,
                       use_available=False,sort_by_zero_oh=True,just_find_need=False, weeks_forecast=6):
    import pandas as pd
    import numpy as np
    import warnings
    warnings.filterwarnings('ignore')
    df = pd.read_excel(file_upload, skiprows=blank_rows(file_upload))

    unwanted_states = ['AK','HI','PR']
    df = df[~df['State'].isin(unwanted_states)]

    available_inventory = pd.read_excel(inventory_upload, skiprows=1) # inventory upload

    # getting the unique list of SKU's and saving it to dataframe
    unique_sku = df['Vendor Stk Nbr'].unique()

    # creating units needed calculation
    df['wk_fcst'] = df.iloc[:,16:weeks_forecast+16].sum(axis=1) # summing each weeks forecast to get a total 6 week forecast
    df['pipe_minus_fcst'] = df.iloc[:, 15] - df['wk_fcst'] # getting pipeline minus forecast
    df['pipe_minus_fcst'] = df.apply(lambda row: 0 if row['pipe_minus_fcst'] > 0 else row['pipe_minus_fcst'], axis=1) # if pipeline minus forecast is greater than 0 make it 0
    df['pipe_minus_fcst'] = df['pipe_minus_fcst'].abs() # getting absolute value of number
    df['whse_pks_needed'] = df['pipe_minus_fcst'] / df['Vnpk Qty'] # converting to vendor packs
    df['whse_pks_needed'] = df['whse_pks_needed'].apply(np.ceil) # rounding up to the nearest whole number
    if use_custom_vendor_packs:
        df['pipe_need'] = df.apply(lambda row: vendor_packs_to_send if row['whse_pks_needed'] > vendor_packs_to_send else row['whse_pks_needed'], axis=1)
        df['pipe_need'] = df.apply(lambda row: vendor_packs_to_send if (row['wk_fcst'] == 0 and row.iloc[11] == 0) else row['pipe_need'], axis=1) # if the store's forecast and on hand is zero make the units need max shelf minus pipeline
    else:
        df['pipe_need'] = df['whse_pks_needed'] * df['Vnpk Qty'] # converting back to units
        df['mx_shelf_minus_pipeline'] = df.apply(lambda row: 0 if row.iloc[5] - row.iloc[15] < 0 else row.iloc[5] - row.iloc[15], axis=1) # if max shelf qty minus pipe is les than 0 make it zero other wise make it the difference between max shelf and the pipe
        df['pipe_need'] = df.apply(lambda row: row.iloc[5] if row['pipe_need'] > row.iloc[5] else row['pipe_need'], axis=1) # if the max shelf qty is less than the needed amount just make it max shelf qty
        df['pipe_need'] = df.apply(lambda row: row['mx_shelf_minus_pipeline'] if (row['wk_fcst'] == 0 and row.iloc[11] == 0) else row['pipe_need'], axis=1) # if the store's forecast and on hand is zero make the units need max shelf minus pipeline
        df['pipe_need'] = df['pipe_need'] / df['Vnpk Qty'] # converting to vendor packs
        df['pipe_need'] = df['pipe_need'].apply(np.ceil) # rounding up to the nearest whole number

    #creating an empty dataframe for the loop
    sto_single = pd.DataFrame()

    for item in unique_sku:
        df_filtered = df[df['Vendor Stk Nbr'] == item]
        df_filtered = df_filtered[df_filtered.iloc[:, 6] == 1] # filtering to only valid stores
        df_filtered = df_filtered[df_filtered['Store Type Descr'] != 'BASE STR Nghbrhd Mkt'] # filtering out Neighborhood Market stores
        if sort_by_zero_oh:
            curr_str_on_hand_qy = df_filtered.iloc[:, 7]
            df_filtered = df_filtered.sort_values(by = [curr_str_on_hand_qy, 'pipe_need'], ascending=[False, False]).reset_index() # sort by stores that have zero on hand and pipe need
        else:
            df_filtered = df_filtered.sort_values('pipe_need', ascending=False).reset_index() # sorting to rank stores with the highest pipe_need

        # getting available inventory 
        blkst_oh = available_inventory[available_inventory['Item'] == item]
        if just_find_need:
            available_inv = float(1000000) # makes the on hand qty 1 million so we can find the need and not be limited by what is on hand
        else:
            if use_available:
                available_inv = float(blkst_oh.iloc[0][7]) / float(blkst_oh.iloc[0][9]) # uses available - split pack (converts to vendor packs)
            else:
                available_inv = float(blkst_oh.iloc[0][2]) / float(blkst_oh.iloc[0][9]) # uses on hand inventory (converts to vendor packs)

        #reducing available inventory for shared items
        shared_items = [1528,4114,5017,5091,5249,5471]
        if item in shared_items:
            available_inv *= 0.5
        else:
            available_inv

        # zero inventory alert
        if available_inv < 0:
            print(f"{item} has no inventory")

        # calculating rolling sum
        df_filtered['vnpks_sent_dc'] = 0

        for i in range(len(df_filtered)):
            try:
                if df_filtered['pipe_need'][i] > available_inv:
                    df_filtered['vnpks_sent_dc'][i] = 0
                elif df_filtered['pipe_need'][i] < available_inv:
                    df_filtered['vnpks_sent_dc'][i] = df_filtered['pipe_need'][i]
                    available_inv -= df_filtered['pipe_need'][i]
            except KeyError:
                pass

        # sorting the dataframe to put units sent at the top
        df_filtered = df_filtered.sort_values(['vnpks_sent_dc'],ascending=False)

        # Dropping rows that where BLKST isn't sending anything. 
        condition1 = (df_filtered['vnpks_sent_dc'] == 0) 
        df_filtered = df_filtered[~(condition1)]

        # selecting columns to keep
        dc_columns = ['Prime Item Nbr', 'Vendor Stk Nbr','Store Nbr','vnpks_sent_dc']

        try:
            sto_single = pd.concat([sto_single,df_filtered[dc_columns]], ignore_index=True)
        except ValueError:
            pass

        # dropping rows where BLKST isn't sending anything
        sto_single = sto_single.loc[sto_single['vnpks_sent_dc'] != 0]

    sto_single = sto_single
    # printing total vnpks sent and number of stores by item
    sum_by_item = sto_single.groupby('Vendor Stk Nbr')['vnpks_sent_dc'].sum()
    store_count_by_item = sto_single.groupby('Vendor Stk Nbr')['vnpks_sent_dc'].count()

    result_df = pd.DataFrame({
        'Total VNPK Sent': sum_by_item,
        'Number of Stores': store_count_by_item
    })
    result_df = result_df.sort_values(by='Total VNPK Sent', ascending=False)

    return result_df, sto_single
