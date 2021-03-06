#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 31 08:14:03 2021
@author: ericberlow

network analysis functions to 
* build network from tags
* decorate nodes with network metrics 
* decroate nodes with tsnw or spring layout coordinates
* plot pdf of network
* convert network nodes and links file  into openmappr format
* create template of node attribute settigns for openmappr 

"""

import sys
import pandas as pd
sys.path.append("../../../Github/Tag2Network/tag2network/Network/")  # add Tag2Network directory
sys.path.append("../../Github/Tag2Network/tag2network/Network")  # add Tag2Network directory
import numpy as np
import BuildNetwork as bn
import DrawNetwork as dn
import networkx as nx
from collections import Counter
from pandas.api.types import is_string_dtype
#from pandas.api.types import is_numeric_dtype



def buildNetworkX(linksdf, id1='Source', id2='Target', directed=False):
    # build networkX graph object from links dataframe with 'Source' and 'Target' ids
    # generate list of links from dataframe
    linkdata = [(getattr(link, id1), getattr(link, id2)) for link in linksdf.itertuples()]
    g = nx.DiGraph() if directed else nx.Graph()
    g.add_edges_from(linkdata)
    return g


def tsne_layout(ndf, ldf):   
    ## add tsne-layout coordinates and draw
    bn.add_layout(ndf, linksdf=ldf, nw=None)
    ndf.rename(columns={"x": "x_tsne", "y": "y_tsne"}, inplace=True)
    return ndf
   
def spring_layout(ndf, ldf, iterations=1000):
    print("Running spring Layout")
    nw = buildNetworkX(ldf)
    # remove isolated nodes and clusters for layout
    giant_component_nodes  = max(nx.connected_components(nw), key = len)
    giant_component = nw.subgraph(giant_component_nodes)
    layout = nx.spring_layout(giant_component, k=0.2, weight='weight', iterations=iterations) # k is spacing 0-1, default 0.1
    x ={n:layout[n][0] for n in giant_component.nodes()}
    y= {n:layout[n][1] for n in giant_component.nodes()}
    ndf['x_spring'] = ndf['id'].map(x)
    ndf['y_spring'] = ndf['id'].map(y)
    # place all disconnected nodes at 0,0
    ndf['x_spring'].fillna(0, inplace=True)
    ndf['y_spring'].fillna(0, inplace=True)
    return ndf

def force_directed(ndf, ldf, iterations=1000):
    ## add force-directed layout coordinate
    bn.add_force_directed_layout(ndf, linksdf=ldf, nw=None, iterations=iterations)
    return ndf

def plot_network(ndf, edf, plot_name, x='x_tsne', y='y_tsne', colorBy='Cluster', sizeBy='ClusterCentrality', sizeScale=100):    
    # draw network colored by creative style and save image
    # ndf = nodes dataframe
    # ldf = links dataframe 
    # plotname = name of file to save image (pdf)
    nw = buildNetworkX(edf) # build networkX graph object
    node_sizes = ndf.loc[:,sizeBy]*sizeScale
    node_sizes_array = node_sizes.values # convert sizeBy col to array for sizing
    dn.draw_network_categorical(nw, ndf, node_attr=colorBy, plotfile=plot_name, x=x, y=y, node_size=node_sizes_array)


def write_network_to_excel (ndf, ldf, outname):
    writer = pd.ExcelWriter(outname,
                          engine='xlsxwriter', 
                          options={'strings_to_urls': False})
    ndf.to_excel(writer,'Nodes', index=False, encoding = 'utf-8-sig')
    ldf.to_excel(writer,'Links', index=False, encoding = 'utf-8-sig')
    writer.save()  



def build_network(df, attr, blacklist=[], idf=False, linksPer=3, minTags=1): 
    '''
    Run basic 'build tag network' without any plotting or layouts or file outputs.
    Resulting network can then be enriched and decorated before writing final files. 
    
    df = nodes dataframe
    attr = tag attribute to use for linking
    blacklist = tags to blacklist from linking
    linksPer = avg links per node
    minTags = exclude any nodes with fewer than min Tags
    
    Returns: nodes and links dataframes
    '''
    print("\nBuild Network")       
    df[attr]=df[attr].fillna("")
    df = df[df[attr]!='']  # remove any recipients which have no tags for linking
    df = df.reset_index(drop=True)
    taglist = attr+"_list" # name new column of tag attribute converted into list
    df[taglist] = df[attr].apply(lambda x: x.split('|')) # convert tag string to list
    df[taglist] = df[taglist].apply(lambda x: [s for s in x if s not in blacklist])   # only keep keywords not in blacklist
    df[attr] = df[taglist].apply(lambda x: "|".join(x)) # re-join tags into string with blacklist removed
    ndf,ldf = bn.buildTagNetwork(df, tagAttr=taglist, dropCols=[], outname=None,
                            nodesname=None, edgesname=None, plotfile=None, #str(networkpath/'RecipientNetwork.pdf'), 
                            idf=idf, toFile=False, doLayout=False, linksPer=linksPer, minTags=1)
    
    return ndf,ldf


def decorate_network(df, ldf, tag_attr, 
                     network_renameDict, # column renaming
                     finalNodeAttrs, # ginal columns to keep
                     outname, # final network file name
                     labelcol,# column to be used for node label
                     writeFile=True, 
                     removeSingletons=True): 
    '''
    Decorate network from 'build_network'
    df = node dataframe (ndf) from build_network
    ldf = links dataframe
    tag_attr = name of tag column used for linking
    outname = name of final network file (excel file)
    writeFile = write final excel file with nodes and links sheets 
    removeSinteltons = trim final keyword tag list to only inlcudes ones that occur at least twice

    Returns: cleaned/decorated nodes datframe plus original links dataframe
    '''
    print("\nDecorating Newtork")
    # tag_attr is the tag attribute used for linking
    
     # Add Cluster Counts, and additional Cluster Labels
    print("Adding Cluster Counts and short Cluser labels")  
    df['Cluster_count'] = df.groupby(['Cluster'])['id'].transform('count') 
    df['Keyword_Theme'] = df['top_tags'].apply(lambda x: ','.join(x[0:3]))# use top 3 wtd tags as short name
    df.drop(['Cluster'], axis=1, inplace=True)

    df['label'] = df[labelcol]
    
    ## add layouts
        ## add tsne layout coordinates
    df = tsne_layout(df, ldf)
        # add force directed layout coordinates
    #df = spring_layout(df, ldf, iterations=500)

    # add outdegree
    nw = buildNetworkX(ldf, directed=True)
    df['n_Neighbors'] = df['id'].map(dict(nw.out_degree()))
    
    if removeSingletons:
        print("Removing singleton keywords")
        #remove singleton tags
        # across entire dataset, count tag hist and remove singleton tags
        taglist_attr = tag_attr+"_list"
        df[taglist_attr].fillna('', inplace=True)
        # build master histogram of tags that occur at least twice 
        tagHist = dict([item for item in Counter([k for kwList in df[taglist_attr] for k in kwList]).most_common() if item[1] > 1])
        # filter tags to only include 'active' tags - tags which occur twice or more in the entire dataset
        df[taglist_attr] = df[taglist_attr].apply(lambda x: [k for k in x if k in tagHist])
        # double check to remove spaces and empty elements
        df[taglist_attr] = df[taglist_attr].apply(lambda x: [s.strip() for s in x if len(s)>0] )
        # join list back into string of unique pipe-sepparated tags
        df[tag_attr] = df[taglist_attr].apply(lambda x: "|".join(list(set(x)))) 
        df['nTags'] = df[tag_attr].apply(lambda x: len(x.split("|")))  
        
    
    
    ## Clean final columns
    print("Cleaning final columns")
                
    df.rename(columns=network_renameDict, inplace=True)
    #df.rename(columns={tag_attr: 'Keywords'}, inplace=True)
 
                # stillneed: 'Geographic_Focus', 'email',         
    df = df[finalNodeAttrs]

    if writeFile:
        print("Writing Cleaned Network File")
        # Write back out to excel with 2 sheets. 
        df = df.reset_index(drop=True)
        write_network_to_excel (df, ldf, outname)
        
    return df, ldf


### MAIN FUNCTION TO BUILD AND DECORATE LINKEDIN AFFINITY NETWORK ###
def build_decorate_plot_network(df, 
                                tag_attr, # tag col for linking
                                linksPer,# links per node
                                blacklist, # tags to blacklist for linjking
                                nw_name, # final filename for network
                                network_renameDict, # rename final node attribs
                                finalNodeAttrs,  # final columns to keep
                                tagcols_nodata, # tag columns to replace empty with 'no data'
                                labelcol='profile_name', 
                                add_nodata = True,
                                plot=True):
    '''
    build and decorate linkedin affinity network
    tagcols: columns to replace empty tags with 'no data' if add_nodata
    Returns:  ndf, ldf and plots/writes pdf of network viz 
    '''
    # Build Network
    ndf, ldf = build_network(df, tag_attr , idf=False, linksPer=linksPer, blacklist= blacklist)
    # Decorate network
    ndf, ldf =  decorate_network(ndf, ldf, tag_attr, 
                                 network_renameDict, # column renaming
                                 finalNodeAttrs, # ginal columns to keep
                                 nw_name, # final network file name
                                 labelcol, 
                                 writeFile=True, 
                                 removeSingletons=True)
    if add_nodata:
        # add 'no data' to empty tags
        for col in tagcols_nodata:
            ndf[col].fillna('no data', inplace=True)
            ndf[col] = ndf[col].apply(lambda x: 'no data' if x == "" else x)
    if plot:
        # Plot Network
        plot_network(ndf, ldf, "Network_plot.pdf", 
                     colorBy = 'Keyword Theme', 
                     sizeBy='ClusterCentrality', 
                     x='x_tsne', y='y_tsne')
    return ndf, ldf

