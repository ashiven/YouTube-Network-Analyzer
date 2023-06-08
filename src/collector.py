from googleapiclient.discovery import build
import re
import networkx as nx
import matplotlib.pyplot as plt
import argparse
import os
from library import hierarchy_pos
from typing import *
import ast
import requests


# this function uses a regular expression to extract the videoId parameter from any youtube link
def parseVideoId(link: str) -> Optional[str]:

    # regular expression for extracting videoId
    regex = r"(?:youtu\.be\/|youtube\.com\/watch\?v=|youtube\.com\/embed\/)([^?&\/]+)"
    res = re.search(regex, link)

    if res:
        videoId = res.group(1)
        return videoId
    else:
        return None

# this function takes a video id and returns the title and channel id for that video
def getVideoInfo(youtube: Any, videoId: str) -> tuple[str, str]:
    response = youtube.videos().list(part='snippet', id=videoId).execute()
    
    return response['items'][0]['snippet']['title'], response['items'][0]['snippet']['channelId']

# this function takes a channel id and returns the name of the channel
def getChannelName(youtube: Any, channelId: str) -> str:
    response = youtube.channels().list(part='snippet', id=channelId).execute()
    return response['items'][0]['snippet']['title']


# this function does the same starting with a video id and using oembed instead of the data api
def getChannelNameEmbed(videoId: str) -> str:
    response = requests.get('https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=' + videoId)
    dict = eval(response.text)
    return dict['author_name']


# this function takes as input a video Id and based on width returns 'width' amount of related videos 
def getRelated(youtube: Any, videoId: str, width: int) -> Dict:
    
    # query youtube api for related videos 
    response = youtube.search().list(
        part = 'snippet',
        relatedToVideoId = videoId,
        maxResults = width,
        type = 'video'
    ).execute()

    # store related videos in a dictionary with key: videoId , value: title
    related = {}
    for item in response['items']:
        title = item['snippet']['title']
        id = item['id']['videoId']
        channelId = item['snippet']['channelId']
        related[id] = [videoId, title, channelId]

    return related


# this function will calculate our layers of related videos by repeatedly calling getRelated() on every video for every layer 
def getLayers(youtube: Any, videoId: str, width: int, depth: int) -> List[Dict]:

    # initialize array that will hold one dictionary per layer
    layers = [{} for _ in range(depth + 1)]
    title, channelId = getVideoInfo(youtube, videoId)
    layers[0] = { videoId : [None, title, channelId] }

    # call getRelated() for retrieving related videos from layer 1 to 'depth'
    for i in range(1, depth + 1):
        if(i == 1):
            layers[i] = getRelated(youtube, videoId, width)
        else:
            for video in layers[i - 1]:
                related = getRelated(youtube, video, width)
                layers[i].update(related)

    return layers


# this function takes our layers and converts them to a dict with key: video Id, value: video Title
def layersToTitleDict(layers: List[Dict]) -> Dict:
    dict = {}
    for layer in layers:
        for key, value in layer.items():
            dict[key] = value[1]

    return dict


# this function takes our layers and converts them to a dict with key: video Id, value: channel Id
def layersToChannelDict(layers: List[Dict]) -> Dict:
    dict = {}
    for layer in layers:
        for key, value in layer.items():
            dict[key] = value[2]

    return dict
    

# this function takes the dictionary from layersToDict() and uses it to return the matching video Title 
def keyToTitle(dict: Dict, videoId: str) -> str:
    if videoId in dict:
        return dict[videoId]
    else:
        return None
    

# this function takes our layers and tree and so on and returns a list with the colors for the tree according to channelIds and a dict labels for labeling nodes with channelIds
def getColors(layers: List[Dict], T: nx.Graph) -> tuple[List[str], Dict]:

    # convert layers to a dictionary with key: videoId, value: channelId
    dict = layersToChannelDict(layers)

    # give every node its appropriate channelId label, replacing its previous videoId labels
    labels = {}
    for node in T.nodes():
        labels[node] = dict[node]

    # create a list of unique channel Ids and then create a list of colors with one color for each channel Id
    uniqueChannelIds = list(set(dict.values()))
    colors = ["gold", "violet", "blue", "silver", #TODO: this is a very shitty and temporary solution and needs to be changed because if we end up needing more colors we're f'd
              "limegreen", "orange", "darkorange",
              "yellow", "green", "red","limegreen", "orange", "darkorange",
              "yellow", "green", "red","gold", "violet", "blue", "silver",
               "limegreen", "orange", "darkorange","yellow", "green", "red",
               "gold", "violet", "blue", "silver",
                "yellow", "green", "red","limegreen", "orange", "darkorange", ]

    # map every channelId to a color and after that map every node in the tree to the color corresponding with its channelId
    channelToColor = {channelId: colors[count] for count, channelId in enumerate(uniqueChannelIds)}
    nodeToColor = {node: channelToColor[labels[node]] for node in T.nodes()}

    # now finally we create the list of colors that will be used for the nodes, red being the default color for undefined channelIds aka the root node
    return [nodeToColor.get(node, 'red') for node in T.nodes()], labels


# this function will convert our layers from a list of dictionaries to a tree which can then be visualized 
def getTree(layers: List[Dict]) -> tuple[nx.Graph, str]:

    # create a new graph with undirected edges
    T = nx.Graph()

    # iterate through layers and add edges according to parent node specified in value[0]
    for layer in layers:
        for key, value in layer.items():
            if not T.has_node(key) and value[0] != None:
                T.add_node(key)
                parentKey = value[0]
                T.add_edge(parentKey, key)
    root = next(iter(layers[1].values()))[0]
    
    return T, root


# this function takes a tree with the node names being video Ids and converts that tree
# into one that is labeled with the respective channel Ids belonging to the video Ids
def convertTree(youtube: Any, T: nx.Graph, root: str, layers: List[Dict], display: str, graph: bool) -> None:
    
    colors, labels = getColors(layers, T)

    if display == 'channelId':
        # draw the graph
        plt.figure(figsize=(15, 10))
        pos = hierarchy_pos(T, root)
        nx.draw(T, pos=pos,  with_labels=False, node_color=colors)
        nx.draw_networkx_labels(T, pos, labels, font_size=9)

        # show plot
        plt.title('Channel Id Tree')
        plt.tight_layout
        plt.show()

    elif display == 'title':
        # convert layers to a dictionary with key: videoId, value: title
        dict = layersToTitleDict(layers)

        # give every node its appropriate title label, replacing its previous videoId labels
        labels = {}
        for node in T.nodes():
            labels[node] = dict[node]

        # draw the graph
        plt.figure(figsize=(15, 10))
        pos = hierarchy_pos(T, root)
        nx.draw(T, pos=pos,  with_labels=False, node_color=colors)
        nx.draw_networkx_labels(T, pos, labels, font_size=9)

        # show plot
        plt.title('Title Tree')
        plt.tight_layout
        plt.show()
    
    elif display == 'channelName':
        # list with unique channel Ids 
        channelIdList = list(set(labels.values()))

        # create dict with key: channelId ,value: channelName
        channelDict = {channelId: getChannelName(youtube, channelId) for channelId in channelIdList}

        # give every node its appropriate channelName label, replacing its previous videoId labels
        channelLabels = {}
        for node in T.nodes():
            channelLabels[node] = channelDict[labels[node]]

        # draw the graph
        plt.figure(figsize=(15, 10))
        pos = hierarchy_pos(T, root)
        nx.draw(T, pos=pos,  with_labels=False, node_color=colors)
        nx.draw_networkx_labels(T, pos, channelLabels, font_size=9)

        # show plot
        plt.title('Channel Name Tree')
        plt.tight_layout
        plt.show()

        if graph:
            G = nx.Graph()

            for edge in T.edges():
                u,v = edge
                U = channelDict[labels[u]]
                V = channelDict[labels[v]]
                if not (U,V) in G.edges() and U != V:
                    G.add_node(U, size=1)
                    G.add_node(V, size=1)
                    G.add_edge(U, V, weight=1)
                elif (U,V) in G.edges():
                    G.edges[U, V]['weight'] += 1

            for node in T.nodes():
                U = channelDict[labels[node]]
                G.nodes[U]['size'] += 1

            nx.write_graphml(G, f'./graphs/{root}.graphml')
            print(f'Created graph: ./graphs/{root}.graphml')
    return
    

# this function imports the trees saved in filename and converts them to a network graph
# this graph will then be saved as import_log.graphml in /graphs
def convertImports(youtube: Any, filename: str) -> None:

    # we basically repeat what we are doing in convertTree() with -D channelName and -g with the trees from the import file
    layerList = []
    with open(f'./data/{filename}', 'r', encoding = 'utf-8') as logfile:
        for line in logfile:
            layers = eval(line)
            layerList.append(layers)

    fileName = None
    G = nx.Graph()
    for count, layers in enumerate(layerList):

        
        T, root = getTree(layers)
        print(f'Importing tree: {count} with root: {root}')

        # some stuff we need 
        dict = layersToChannelDict(layers)
        labels = {}
        for node in T.nodes():
            labels[node] = dict[node]
        #channelIdList = list(set(labels.values()))
        #channelDict = {channelId: getChannelName(youtube, channelId) for channelId in channelIdList}

        # use the embed version for large graphs that might exhaust the data api in their creation
        videoIdTochannelName = {videoId: [getChannelNameEmbed(videoId), dict[videoId]] for videoId in T.nodes()}
        channelDict = { channelId: channelName for channelName, channelId in videoIdTochannelName.values() }

        # we use the root of the first tree as the filename
        if fileName == None:
            fileName = channelDict[labels[root]]
                    
        for edge in T.edges():
            u,v = edge
            U = channelDict[labels[u]]
            V = channelDict[labels[v]]
            if not (U,V) in G.edges() and U != V:
                G.add_node(U, size=1)
                G.add_node(V, size=1)
                G.add_edge(U, V, weight=1)
            elif (U,V) in G.edges():
                G.edges[U, V]['weight'] += 1

        for node in T.nodes():
            U = channelDict[labels[node]]
            G.nodes[U]['size'] += 1

    fileName = re.sub(r'\s+', '_', fileName)
    fileName = re.sub(r'[^\w\s-]', '', fileName)
    nx.write_graphml(G, f'./graphs/{fileName}.graphml')
    print(f'Created graph: ./graphs/{fileName}.graphml')
    return 


# this function takes a rootLine indicating where the tree, whose leafs we are trying to convert into trees, is located in the file
def getLeafTrees(rootLine: int, leaf: int, youtube: Any, width: int, depth: int, videoId: str) -> bool:

    # open file in read mode
    with open(f'./data/{videoId}.log', 'r', encoding = 'utf-8') as logfile:
        for i, l in enumerate(logfile):
            # read the tree in rootLine and get the leafs for that tree
            if i == rootLine:
                rootLayers = eval(l)
                leafDict = rootLayers[-1]
                leafIds = list(leafDict.keys())

    with open(f'./data/{videoId}.log', 'a', encoding = 'utf-8') as logfile:
        # append the leaf trees to the file
        for count, leafId in enumerate(leafIds):
            if count >= leaf:
                try:
                    layers = getLayers(youtube, leafId, width, depth)
                    print(layers, file=logfile)
                    print(f'Saved leafTree: {count}')
                except:
                    with open(f'./data/{videoId}_breakpoint.txt', 'w') as file:
                        file.write(str(rootLine))
                        file.write('\n')
                        file.write(str(count))

                    print('Seems like the quota has been exceeded :(')
                    return False
    return True


# this function keeps calling getLeafTrees until the quota has been exceded
def forceUntilQuota(line: int, leaf: int, youtube: Any, width: int, depth: int, videoId: str) -> None:
    loop = True
    while(loop):
        print(f'Calling getLeafTrees({line})...')
        loop = getLeafTrees(line, leaf, youtube, width, depth, videoId)
        line += 1


def getTitles(filename: str) -> None:

    # Load the file
    with open(f'./data/{filename}', 'r') as file:
        data = file.read()

    # Convert the string representation to a list of dictionaries
    data_list = ast.literal_eval(data)

    # Extract the titles of YouTube videos
    titles = []
    for item in data_list:
        for video_id, details in item.items():
            title = details[1]
            titles.append(title)

    # Save the titles to titles.log
    with open(f'./titles/{filename}', 'w') as file:
        for title in titles:
            file.write(title + '\n')

    print(f'Extracted titles: ./titles/{filename}')


def main():

    # parse the arguments supplied by the user
    parser = argparse.ArgumentParser(description='Youtube Related Video Collector')
    parser.add_argument('-d', '--depth', type=int, default=2, help='Search Depth')
    parser.add_argument('-w', '--width', type=int, default=3, help='Search Width')
    parser.add_argument('-s', '--seed', type=str, help='Initial Youtube Video Link')
    parser.add_argument('-D', '--display', type=str, default='title', help="Display Video Titles: 'title' | Video Ids: 'videoId' | Channel Ids: 'channelId'")
    parser.add_argument('-l', '--log', action='store_true', help="Store the tree inside of a log file")
    parser.add_argument('-g', '--graph', action='store_true', help="Whether to convert the tree to a graph that will be exported to a graphML file(only works with -D channelName)")
    parser.add_argument('-i', '--treeimport', type=str, default=None, help="Import the trees for a given file and convert them to a graph")
    parser.add_argument('-f', '--force', action='store_true', help="Keep calculating trees and storing them in the specific file until the quota is exceeded")
    parser.add_argument('-t', '--titles', type=str, default=None, help="Extract only the titles from a given file")
    args = parser.parse_args()

    seed = args.seed 
    width = args.width
    depth = args.depth
    display = args.display
    log = args.log
    graph = args.graph
    treeimport = args.treeimport
    force = args.force
    titles = args.titles
    videoId = None
    if(seed):
        videoId = parseVideoId(seed)


    # here we have a few api keys because the ratelimiting is bad...
    apiKey = '***REMOVED***'      # Jannik
    apiKey2 = '***REMOVED***'     # Jannik
    apiKey3 = '***REMOVED***'     # Jonathan
    apiKey4 = '***REMOVED***'     # Gunnar
    apiKey5 = '***REMOVED***'     # Gunnar
    apiKey6 = '***REMOVED***'     # Elena
    apiKey7 = '***REMOVED***'     # Elena
    apiKey8 = '***REMOVED***'     # Egemen
    apiKey9 = '***REMOVED***'     # Egemen



    # we create the youtube object for interacting with the API and getLayers() to retrieve the layers of related videos
    youtube = build('youtube', 'v3', developerKey=apiKey)
    if not treeimport and not force and not titles:
        layers = getLayers(youtube, videoId, width, depth)

        # write the result for layers into a log file 
        if log:
            with open(f'./data/{videoId}.log', 'a', encoding='utf-8') as logfile:
                print(layers, file=logfile)
    

    # display video ids as node labels
    if display == 'videoId':
        T, root = getTree(layers)
        colors = getColors(layers, T)[0]

        # draw the graph
        plt.figure(figsize=(15, 10))
        pos = hierarchy_pos(T, root)
        nx.draw(T, pos=pos,  with_labels=True, font_size=9, node_color=colors)
        plt.title('Related Videos')
        plt.tight_layout
        plt.show()


    # display video titles as node labels
    elif (display == 'title' or display == 'channelId' or display == 'channelName') and not treeimport and not force and not titles:
        T, root = getTree(layers) 
        convertTree(youtube, T, root, layers, display, graph)


    # import/convert trees saved in treeimport
    elif treeimport:
        convertImports(youtube, treeimport)


    # calculate trees until the quota is exceeded and save the stopping point in {videoId}_breakpoint.txt
    elif force:
        if not os.path.isfile(f'./data/{videoId}.log'):
            open(f'./data/{videoId}.log', "w", encoding='utf-8').close()

        with open(f'./data/{videoId}.log', 'r', encoding='utf-8') as logfile:
            linecount = sum(1 for _ in logfile)
        
        if linecount == 0:
            layers = getLayers(youtube, videoId, width, depth)
            with open(f'./data/{videoId}.log', 'a', encoding='utf-8') as logfile:
                print(layers, file=logfile)
            print('Starting tree calculation...')
            forceUntilQuota(0, 0, youtube, width, depth, videoId)
        
        else: 
            with open(f'./data/{videoId}_breakpoint.txt', 'r') as file:
                for i, l in enumerate(file):
                    if i == 0:
                        line = l
                    if i == 1:
                        leaf = l
            line = int(line.strip())
            leaf = int(leaf.strip())
            print(f'Continuing tree calculation from line: {line} - leaf: {leaf}')
            forceUntilQuota(line, leaf, youtube, width, depth, videoId)


    elif titles:
        getTitles(titles)


    # invalid arguments
    else:
        parser.print_usage()


if __name__ == '__main__':
    try:
        main()
    except:
        print('seems like the quota has been exceeded :(')