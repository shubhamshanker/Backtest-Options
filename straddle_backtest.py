# import libraries
import pandas as pd
import datetime
import numpy as np
import matplotlib.pyplot as plt
from glob import glob
from dateutil.relativedelta import relativedelta, TH

# fetch all files from directory
path = pd.DataFrame(glob('/Users/admin/Downloads/sample_nfo_2019-20_data/*'), columns = ['location'])
path['data_date'] = path['location'].apply(lambda x:x.split("_")[-1].split('.')[0])
path['data_date'] = path['data_date'].apply(lambda x: datetime.datetime.strptime(x,"%Y-%m-%d"))
path.sort_values(['data_date'],inplace=True)
path.reset_index(drop = True, inplace=True)
path['data_date'].iloc[0]

intraday_trade_log = pd.DataFrame(columns=['Entry_Datetime', 'FTP', 'ATM', 'Days_To_Expiry', 'CE_Symbol', 'CE_Entry_Price', 'CE_Exit_Price', 'CE_Exit_Datetime', 'PE_Symbol', 'PE_Entry_Price', 'PE_Exit_Price', 'PE_Exit_Datetime', 'PnL'])



# Short Straddle - can vary stop loss and entry/exit timings

for index, row in path.iterrows():
    try:
        print(index)
        # read data 
        data = pd.read_pickle(row['location'])

        # get the timings from data
        entry_datetime = datetime.datetime.combine(row['data_date'].date(), datetime.time(9,17))
        exit_datetime = datetime.datetime.combine(row['data_date'].date(), datetime.time(15,10))

        # Current Expiry
        # Next Month Expiry 
        # Next to Next Month Expiry
        data['expiry_type'] = np.where((data['instrument_type'] == 'FUT'),data['ticker'].apply(lambda x: x.split('-')[-1].split('.')[0]),'')

        future_offset_expiry = "I"
        instrument = 'BANKNIFTY'
        base = 100
        futures_data = data[(data['instrument_type'] == 'FUT') & (data['instrument_name'] == instrument) & (data['expiry_type'] == future_offset_expiry)]
        futures_data.reset_index(drop=True, inplace=True)

        atm = futures_data[futures_data['datetime'] == entry_datetime]['open'].iloc[0]
        atm = base*round(atm/base)
        print(atm)

        nearest_expiry = row['data_date'].date()+  relativedelta(weekday=TH(+1))
        print(nearest_expiry)

        ce_data = data[(data['instrument_type'] =='CE') & (data['instrument_name'] == instrument) & ((data['expiry_date'] == nearest_expiry)|(data['expiry_date'] == nearest_expiry-datetime.timedelta(days=1))|(data['expiry_date'] == nearest_expiry-datetime.timedelta(days=2))) & (data['strike_price'] == atm)]
        ce_data.reset_index(drop=True, inplace=True)
        pe_data = data[(data['instrument_type'] =='PE') & (data['instrument_name'] == instrument) & ((data['expiry_date'] == nearest_expiry)|(data['expiry_date'] == nearest_expiry-datetime.timedelta(days=1))|(data['expiry_date'] == nearest_expiry-datetime.timedelta(days=2))) & (data['strike_price'] == atm)]
        pe_data.reset_index(drop=True, inplace=True)

        ce_symbol = ce_data['ticker'].iloc[0]
        pe_symbol = pe_data['ticker'].iloc[0]

        futures_data = futures_data[['datetime', 'close']].set_index('datetime')
        ce_data = ce_data[['datetime', 'close']].set_index('datetime')
        pe_data = pe_data[['datetime', 'close']].set_index('datetime')
        intraday_data = pd.concat([futures_data, ce_data, pe_data], axis = 1)


        intraday_data.columns = ['futures_close', 'ce_close' , 'pe_close']
        intraday_data.ffill()
        intraday_data.reset_index(inplace=True)


        traded_prices = intraday_data[intraday_data['datetime'] == entry_datetime]
        print(traded_prices)
        futures_entry_price = traded_prices['futures_close'].iloc[0]
        ce_entry_price = traded_prices['ce_close'].iloc[0]
        pe_entry_price = traded_prices['pe_close'].iloc[0]

        stop_loss_percentage =40/100
        ce_stop_loss = ce_entry_price + ce_entry_price*stop_loss_percentage;
        pe_stop_loss = pe_entry_price + pe_entry_price*stop_loss_percentage
        entry_time_index = intraday_data[intraday_data['datetime'] == entry_datetime].index[0]
        exit_time_index = intraday_data[intraday_data['datetime'] == exit_datetime].index[0]
        intraday_data = intraday_data[entry_time_index : exit_time_index+1]
        intraday_data['ce_pnl'] = 0
        intraday_data['pe_pnl'] = 0
        intraday_data.reset_index(drop=True,inplace=True)

        ce_stop_loss_counter = 0
        pe_stop_loss_counter = 0
        ce_exit_datetime = ''
        pe_exit_datetime = ''
        ce_exit_price = 0
        pe_exit_price = 0
        ce_pnl = 0
        pe_pnl = 0
        pnl = 0

        for index,row in intraday_data.iterrows():
            ce_ltp = row['ce_close']
            pe_ltp = row['pe_close']
            #print(f'@{row["datetime"]}::{ce_ltp}::{pe_ltp}')
    #       if no stop losses are hit till exit time
            if (ce_stop_loss_counter == 0) & (pe_stop_loss_counter == 0) & (row['datetime'] == exit_datetime):
                ce_pnl = ce_entry_price - ce_ltp
                pe_pnl = pe_entry_price - pe_ltp

                ce_stop_loss_counter = 1
                pe_stop_loss_counter = 1
                ce_exit_datetime = row['datetime']
                pe_exit_datetime = row['datetime']
                ce_exit_price = ce_ltp
                pe_exit_price = pe_ltp

                intraday_data.loc[index, 'ce_pnl'] = ce_pnl
                intraday_data.loc[index, 'pe_pnl'] = pe_pnl 
                print('No stoplosses hit till exit time')
                pnl = ce_pnl + pe_pnl
                break

            # ce sl hit first
            elif (ce_ltp >= ce_stop_loss) & (ce_stop_loss_counter == 0) & (pe_stop_loss_counter == 0):

                ce_pnl = ce_entry_price - ce_stop_loss
                pe_pnl = pe_entry_price - pe_ltp

                ce_stop_loss_counter = 1
                ce_exit_datetime = row['datetime']
                ce_exit_price = ce_stop_loss 

                intraday_data.loc[index, 'ce_pnl'] = ce_pnl
                intraday_data.loc[index, 'pe_pnl'] = pe_pnl 

                print('CE sl hit first')
                pnl = ce_pnl + pe_pnl



            # pe sl hit first
            elif (pe_ltp >= pe_stop_loss) & (pe_stop_loss_counter == 0) & (ce_stop_loss_counter == 0):

                ce_pnl = ce_entry_price - ce_ltp
                pe_pnl = pe_entry_price - pe_stop_loss

                pe_stop_loss_counter = 1
                pe_exit_datetime = row['datetime']
                pe_exit_price = pe_stop_loss 

                intraday_data.loc[index, 'ce_pnl'] = ce_pnl
                intraday_data.loc[index, 'pe_pnl'] = pe_pnl 

                print('PE sl hit first')
                pnl = ce_pnl + pe_pnl



            # pe sl hit after ce sl
            elif (ce_stop_loss_counter == 1) & (pe_stop_loss_counter == 0):

                if(pe_ltp >= pe_stop_loss) & (row['datetime'] < exit_datetime):

                    pe_pnl = pe_entry_price - pe_stop_loss
                    pe_stop_loss_counter = 1
                    pe_exit_datetime = row['datetime'] 
                    pe_exit_price = pe_stop_loss 
                    intraday_data.loc[index, 'ce_pnl'] = ce_pnl
                    intraday_data.loc[index, 'pe_pnl'] = pe_pnl 
                    pnl = ce_pnl + pe_pnl
                    print('PE sl hit second after CE sl hit')
                    break 

                elif (row['datetime'] == exit_datetime):

                    pe_pnl = pe_entry_price - pe_ltp
                    pe_stop_loss_counter = 1
                    pe_exit_datetime = row['datetime'] 
                    pe_exit_price = pe_ltp 
                    intraday_data.loc[index, 'ce_pnl'] = ce_pnl
                    intraday_data.loc[index, 'pe_pnl'] = pe_pnl 
                    pnl = ce_pnl + pe_pnl
                    print('Only CE sl hit')
                    break


            # ce sl hit after pe sl
            elif(ce_stop_loss_counter == 0) & (pe_stop_loss_counter == 1):

                if(ce_ltp >= ce_stop_loss) & (row['datetime'] < exit_datetime):

                    ce_pnl = ce_entry_price - ce_stop_loss
                    ce_stop_loss_counter = 1
                    ce_exit_datetime = row['datetime'] 
                    ce_exit_price = ce_stop_loss 
                    intraday_data.loc[index, 'ce_pnl'] = ce_pnl
                    intraday_data.loc[index, 'pe_pnl'] = pe_pnl
                    pnl = ce_pnl + pe_pnl
                    print('CE sl hit second after PE sl hit')
                    break 

                elif (row['datetime'] == exit_datetime):

                    ce_pnl = ce_entry_price - ce_ltp
                    ce_stop_loss_counter = 1
                    ce_exit_datetime = row['datetime'] 
                    ce_exit_price = ce_ltp 
                    intraday_data.loc[index, 'ce_pnl'] = ce_pnl
                    intraday_data.loc[index, 'pe_pnl'] = pe_pnl 
                    pnl = ce_pnl + pe_pnl
                    print('Only PE sl hit')
                    break 


            # update pnl in all cases -
            elif (((ce_stop_loss_counter == 0) & (pe_stop_loss_counter == 0)) | ((ce_stop_loss_counter == 1) & (pe_stop_loss_counter == 0))  | ((ce_stop_loss_counter == 0) & (pe_stop_loss_counter == 1)) | ((ce_stop_loss_counter == 1) & (pe_stop_loss_counter == 1))) or row['datetime'] <= exit_datetime:

                ce_pnl = ce_entry_price - ce_ltp
                pe_pnl = pe_entry_price - pe_ltp

                intraday_data.loc[index,'ce_pnl'] = ce_pnl
                intraday_data.loc[index,'pe_pnl'] = pe_pnl

                pnl = ce_pnl + pe_pnl



        print("CE PNL : ", ce_pnl)
        print("PE PNL : ", pe_pnl)
        print("Total PNL : ", pnl)        
        intraday_trade_log = intraday_trade_log.append({'Entry_Datetime':entry_datetime,
                                                            'FTP':futures_entry_price,
                                                            'ATM':atm,
                                                            'Days_to_Expiry':(nearest_expiry - entry_datetime.date()).days,
                                                            'CE_Symbol':ce_symbol,
                                                            'CE_Entry_Price':ce_entry_price,
                                                            'CE_Exit_Price':ce_exit_price,
                                                            'CE_Exit_Datetime':ce_exit_datetime,
                                                            'PE_Symbol':pe_symbol,
                                                            'PE_Entry_Price':pe_entry_price,
                                                            'PE_Exit_Price':pe_exit_price,
                                                            'PE_Exit_Datetime':pe_exit_datetime,
                                                            'PnL':pnl},ignore_index=True)

    except Exception as e:
        print("Exception : ")
        print(e)
        print(row['location'])

intraday_trade_log['PnL'].cumsum().plot()
intraday_trade_log
