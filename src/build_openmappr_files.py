#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 31 08:14:03 2021

@author: ericberlow
"""

import sys
import pandas as pd
import numpy as np
from pandas.api.types import is_string_dtype
#from pandas.api.types import is_numeric_dtype




def write_network_to_excel (ndf, ldf, outname):
    writer = pd.ExcelWriter(outname,
                          engine='xlsxwriter', 
                          options={'strings_to_urls': False})
    ndf.to_excel(writer,'Nodes', index=False, encoding = 'utf-8-sig')
    ldf.to_excel(writer,'Links', index=False, encoding = 'utf-8-sig')
    writer.save()  

def get_default_column_types_openmappr(ndf):
    typeDict = {} # dictionary of column name: (attrType, renderType, searchable) 
    countThresh = 0.02*len(ndf) # number of records to evaluate type (e.g. 2% of total)
    for col in ndf.columns.tolist():
        if is_string_dtype(ndf[col]):
            typeDict[col] = ("string", "wide-tag-cloud", "TRUE")  # fill all strings, then below modify specific ones
        if sum(ndf[col].apply(lambda x: len(str(x)) > 100)) > countThresh: # long text
            typeDict[col] = ("string", "text", "TRUE")
        if sum(ndf[col].apply(lambda x:"http" in str(x))) > countThresh: # urls
            typeDict[col] = ("url", "default", "FALSE")
        if sum(ndf[col].apply(lambda x:"|" in str(x))) > countThresh:  # tags
            typeDict[col] = ("liststring", "tag-cloud", "TRUE")
        if sum(ndf[col].apply(lambda x:"png" in str(x))) > countThresh: # images
            typeDict[col] = ("picture", "default", "FALSE") 
            typeDict[col] = ("picture", "default", "FALSE")                 
        if ndf[col].dtype == 'float64':           # float
            typeDict[col] = ("float", "histogram", "FALSE")
        if ndf[col].dtype == 'int64':             # integer
            typeDict[col] = ("integer", "histogram", "FALSE")
        if ndf[col].dtype == np.int64: #'Int64':             # integer
            typeDict[col] = ("integer", "histogram", "FALSE")
        if ndf[col].dtype == 'bool':             # integer
            typeDict[col] = ("string", "tag-cloud", "FALSE")
        
        #TODO:  need to add timestamp, year, video
    return typeDict
        
    
def write_openmappr_files(ndf, ldf, datapath, labelCol='Name', 
                    hide_add = [],  # list custom attributes to hide from filters
                    hideProfile_add =[], # list custom attributes to hide from right profile
                    hideSearch_add = [], # list custom attributes to hide from search
                    liststring_add = [], # list attributes to treat as liststring 
                    tags_add = [],  # list of custom attrubtes to render as tag-cloud
                    wide_tags_add = [], # list of custom attribs to render wide tag-cloud
                    text_str_add = [],  # list of custom attribs to render as long text in profile
                    email_str_add = [], # list of custom attribs to render as email link
                    showSearch_add = [] # list of custom attribs to show in search
                    ):  
    '''
    Write files for py2mappr: 
        nodes.csv
        links.csv
        node_attrs_template.csv (template for specifying attribute rendering settings in openmappr)
        line_att
    '''
    print('\nWriting openMappr files')
    ## generate csv's for py2mappr

    # prepare and write nodes.csv
    ndf['label'] = ndf[labelCol] 
    ndf['OriginalLabel'] = ndf['label']
    ndf['OriginalX'] = ndf['x_tsne']
    ndf['OriginalY'] = ndf['y_tsne']
    ndf['OriginalSize'] = 10

    ndf.to_csv(datapath/"nodes.csv", index=False)

    # prepare and write links.csv
    ldf['isDirectional'] = True
    ldf.to_csv(datapath/"links.csv", index=False)

    # prepare and write note attribute settings template (node_attrs_template.csv)
        
       # create node attribute metadata template:
    node_attr_df = ndf.dtypes.reset_index()
    node_attr_df.columns = ['id', 'dtype']


        # map automatic default attrType, renderType, searchable based on column types
        # get dictionary of default mapping of column to to attrType, renderType, searchable
    typeDict =  get_default_column_types_openmappr(ndf)  
    node_attr_df['attrType'] = node_attr_df['id'].apply(lambda x: typeDict[x][0])
    node_attr_df['renderType'] = node_attr_df['id'].apply(lambda x: typeDict[x][1])
    node_attr_df['searchable'] = node_attr_df['id'].apply(lambda x: typeDict[x][2])

        # custom string renderType settings for string attributes
    node_attr_df['attrType'] = node_attr_df.apply(lambda x: 'liststring' if str(x['id']) in liststring_add
                                                               else 'string' if str(x['id']) in (text_str_add + email_str_add)
                                                               else x['attrType'], axis=1)

    node_attr_df['renderType'] = node_attr_df.apply(lambda x: 'wide-tag-cloud' if str(x['id']) in wide_tags_add 
                                                               else 'tag-cloud' if str(x['id']) in tags_add
                                                               else 'text' if str(x['id']) in text_str_add
                                                               else 'email' if str(x['id']) in email_str_add
                                                               else x['renderType'], axis=1)
       # additional attributes to hide from filters
    hide = list(set(['label', 'OriginalLabel', 'OriginalSize', 'OriginalY', 'OriginalX', 'id'] + hide_add))
    node_attr_df['visible'] = node_attr_df['id'].apply(lambda x: 'FALSE' if str(x) in hide else 'TRUE')
 
       # additional attributes to hide from profile
    hideProfile = list(set(hide + hideProfile_add))
    node_attr_df['visibleInProfile'] = node_attr_df['id'].apply(lambda x: 'FALSE' if str(x) in hideProfile else 'TRUE')
    
       # additional attributes to hide from search
    hideSearch = list(set(hide + hideSearch_add))
    node_attr_df['searchable'] = node_attr_df.apply(lambda x: 'FALSE' if str(x['id']) in hideSearch else x['searchable'], axis=1)
    node_attr_df['searchable'] = node_attr_df.apply(lambda x: 'TRUE' if str(x['id']) in text_str_add else x['searchable'], axis=1)
    

       # add default alias title and node metadata description columns
    node_attr_df['title'] = node_attr_df['id']
    defaultcols = ['descr', 'maxLabel', 'minLabel', 'overlayAnchor']
    for col in defaultcols: 
        node_attr_df[col] = ''   

       # re-order final columns and write template file
    meta_cols = ['id', 'visible', 'visibleInProfile', 'searchable', 'title', 'attrType', 'renderType', 'descr', 'maxLabel', 'minLabel', 'overlayAnchor']
    node_attr_df = node_attr_df[meta_cols]
    node_attr_df.to_csv(datapath/"node_attrs.csv", index=False)

#####################################################################################
####  THIS FUNCTION IS A WORK IN PROGRESS -
#### MAKE ALL SETTING MANUALLY DEFINED RATHER THAN TRY TO AUTOMATE

def write_openmappr_files_manual(ndf, ldf, datapath, labelCol='Name', 
                    hideFilters = [],  # list custom attributes to hide from filters
                    hideProfile =[], # list custom attributes to hide from right profile
                    hideSearch = [], # list custom attributes to hide from search
                    ### attr types
                    strings = [], # list attributes to treat as strings 
                    liststrings = [],  # list of  attrubtes to treat as tags (list-string)
                    floats = [], # list of attributes that are float
                    integers = [], 
                    years = [],
                    timestamps = [],
                    photos = [],
                    url = [],
                    videos = [],
                    ### render types
                    tag_cloud = [], # list of custom string attribs to render as small tag-cloud
                    wide_tags_add = [], # list of custom string attribs to render wide tag-cloud
                    text_str_add = [],  # list of custom attribs to render as long text in profile
                    email_str = [], # list of string attribs to render as email
                    histograms = [], # list of attribs to render as histogram. 
                    default_render = [], 
                    ):  

    # Write files for py2mappr: 
        # nodes.csv, links.csv, 
        #node_attrs_template.csv (template for specifying attribute rendering settings in openmappr)

    print('\nWriting openMappr files')
    ## generate csv's for py2mappr
    # prepare and write nodes.csv
    ndf['label'] = ndf[labelCol] 
    ndf['OriginalLabel'] = ndf['label']
    ndf['OriginalX'] = ndf['x_tsne']
    ndf['OriginalY'] = ndf['y_tsne']
    ndf['OriginalSize'] = 10

    ndf.to_csv(datapath/"nodes.csv", index=False)

    # prepare and write links.csv
    ldf['isDirectional'] = True
    ldf.to_csv(datapath/"links.csv", index=False)

    # prepare and write note attribute settings template (node_attrs_template.csv)
        
       # create node attribute metadata template:
    node_attr_df = ndf.dtypes.reset_index()
    node_attr_df.columns = ['id', 'dtype']


        # map automatic default attrType, renderType, searchable based on column types
        # get dictionary of default mapping of column to to attrType, renderType, searchable
    typeDict =  get_default_column_types_openmappr(ndf)  
    node_attr_df['attrType'] = node_attr_df['id'].apply(lambda x: typeDict[x][0])
    node_attr_df['renderType'] = node_attr_df['id'].apply(lambda x: typeDict[x][1])
    node_attr_df['searchable'] = node_attr_df['id'].apply(lambda x: typeDict[x][2])
  
        # custom string renderType settings for string attributes
    node_attr_df['attrType'] = node_attr_df.apply(lambda x: 'liststring' if str(x['id']) in liststring_add
                                                               else 'text' if str(x['id']) in text_str_add 
                                                               else x['attrType'], axis=1)

    node_attr_df['renderType'] = node_attr_df.apply(lambda x: 'wide-tag-cloud' if str(x['id']) in wide_tags_add 
                                                               else 'tag-cloud' if str(x['id']) in tags_add
                                                               else 'text' if str(x['id']) in text_str_add
                                                               else x['renderType'], axis=1)
       # additional attributes to hide from filters
    hide = list(set(['label', 'OriginalLabel', 'OriginalSize', 'OriginalY', 'OriginalX', 'id'] + hide_add))
    node_attr_df['visible'] = node_attr_df['id'].apply(lambda x: 'FALSE' if str(x) in hide else 'TRUE')
 
       # additional attributes to hide from profile
    hideProfile = list(set(hide + hideProfile_add))
    node_attr_df['visibleInProfile'] = node_attr_df['id'].apply(lambda x: 'FALSE' if str(x) in hideProfile else 'TRUE')
    
       # additional attributes to hide from search
    hideSearch = list(set(hide + hideSearch_add))
    node_attr_df['searchable'] = node_attr_df.apply(lambda x: 'FALSE' if str(x['id']) in hideSearch else x['searchable'], axis=1)
    node_attr_df['searchable'] = node_attr_df.apply(lambda x: 'TRUE' if str(x['id']) in text_str_add else x['searchable'], axis=1)

       # add default alias title and node metadata description columns
    node_attr_df['title'] = node_attr_df['id']
    node_attr_df[['descr', 'maxLabel', 'minLabel', 'overlayAnchor']] = ''   
    node_attr_df[['descr', 'maxLabel', 'minLabel', 'overlayAnchor']] = ''

       # re-order final columns and write template file
    meta_cols = ['id', 'visible', 'visibleInProfile', 'searchable', 'title', 'attrType', 'renderType', 'descr', 'maxLabel', 'minLabel', 'overlayAnchor']
    node_attr_df = node_attr_df[meta_cols]
    node_attr_df.to_csv(datapath/"node_attrs.csv", index=False)
#####################################################################################


        
if __name__ == '__main__':
    # test script
    nw_name = "name_of_network_file.xlsx"
    df = pd.read_excel('test_data.xlsx', engine='openpyxl')
 
    ndf = pd.read_excel(nw_name, engine='openpyxl', sheet_name = 'Nodes') # projects funding
    ldf = pd.read_excel(nw_name, engine='openpyxl', sheet_name = 'Links') # projects funding
    
    write_openmappr_files(ndf, ldf, ref.openMappr_path)
    
    