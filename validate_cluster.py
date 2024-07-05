

# this script will validate the cluster and give recommendations on following grounds:

# check if any template other than default is present in cluster and has replication setting and refresh interval configured


# check if any index other than .kibana is present in cluster and has replication setting and refresh interval configured

# check index wise replication setting , refresh interval, health , status, amount of data per shard and recommend increasing or decreasing number of shards to improve performance


# check cluster wide config like max transfer speed, max concurrent shards etc and recommend changes to improve performance


# check node wise disk usage, number of shards per node and alert if any node is overloaded or reaching max shard capacity


# this script will be structured in such a way that a module will be created to collect the data and another module will use it to generate recommendations and alerts

# all the individual analysis modules will return an array with relevant details and must mandatorily contain message, type and related info

import requests
import httpie
from curlify import to_curl
import json
from json2html import *

import requests
import json
import argparse
import time
import logging
from tqdm import tqdm

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# API call throttling
class APIThrottle:
    def __init__(self, calls_per_second):
        self.calls_per_second = calls_per_second
        self.last_call = 0

    def wait(self):
        current_time = time.time()
        time_since_last_call = current_time - self.last_call
        if time_since_last_call < 1 / self.calls_per_second:
            time.sleep((1 / self.calls_per_second) - time_since_last_call)
        self.last_call = time.time()

throttle = APIThrottle(10)  # Limit to 10 calls per second


def getAllIndices(cluster_url="http://localhost:9200"):
    indices = []
    url = "{}/_cat/indices?format=json".format(cluster_url)
    response = requests.get(url)
    if response.status_code == 200:
        for index in response.json():
            indices.append(index['index'])
    return indices

"""
index settings are retrieved in this way
curl -H 'User-Agent: python-requests/2.31.0' 'http://orderes-staging.paytm.internal/mktorders-10005/_settings?pretty'
{
  "mktorders-10005" : {
    "settings" : {
      "index" : {
        "routing" : {
          "allocation" : {
            "include" : {
              "_tier_preference" : "data_content"
            }
          }
        },
        "number_of_shards" : "1",
        "provided_name" : "mktorders-10005",
        "creation_date" : "1697014386369",
        "number_of_replicas" : "1",
        "uuid" : "8v7y0mqtR1GcIlM2acmH1Q",
        "version" : {
          "created" : "8070099"
        }
      }
    }
  }
}
"""

def getIndexLevelSettings(index, cluster_url="http://localhost:9200"):
    url = "{}/{}/_settings".format(cluster_url, index)
    response = requests.get(url)
    # print(to_curl(response.request))
    if response.status_code == 200:
        index_dict = {}
        index_dict['number_of_replicas'] =  response.json()[index]['settings']['index'].get('number_of_replicas')
        index_dict['refresh_interval'] =  response.json()[index]['settings']['index'].get('refresh_interval',0)
        index_dict['number_of_shards'] =  response.json()[index]['settings']['index'].get('number_of_shards',0)
        index_dict['creation_date'] =  response.json()[index]['settings']['index'].get('creation_date',0)        
        return index_dict
    else:
        return {}


"""
index details are retrieved in this way
curl -X GET  -H 'Connection: keep-alive' -H 'User-Agent: python-requests/2.31.0' 'http://orderes-staging.paytm.internal/_cat/indices/mktorders-10005?format=json&pretty'
[
  {
    "health" : "green",
    "status" : "open",
    "index" : "mktorders-10005",
    "uuid" : "8v7y0mqtR1GcIlM2acmH1Q",
    "pri" : "1",
    "rep" : "1",
    "docs.count" : "33010",
    "docs.deleted" : "780",
    "store.size" : "19.5mb",
    "pri.store.size" : "9.7mb"
  }
]
"""
def getIndexDetails(index, cluster_url="http://localhost:9200"):
    url = "{}/_cat/indices/{}?format=json".format(cluster_url, index)
    response = requests.get(url)
    if response.status_code == 200:
        # print(to_curl(response.request))
        if(len(response.json())>0):
            return response.json()[0]
        else:
            return {}


"""
output of index level data will be in this format

{
  "dashboard-2017-7-86": {
    "number_of_replicas": "1",
    "refresh_interval": 0,
    "number_of_shards": "1",
    "creation_date": "1696577452230",
    "health": "green",
    "status": "open",
    "index": "dashboard-2017-7-86",
    "uuid": "sHaZ_Y8MTTSw0mFvhSuchg",
    "pri": "1",
    "rep": "1",
    "docs.count": "10",
    "docs.deleted": "0",
    "store.size": "103.6kb",
    "pri.store.size": "69.4kb"
  }
}

"""
def gatherIndexLevelData(cluster_url="http://localhost:9200"):
    indices = getAllIndices(cluster_url)
    # print(indices)
    index_data = {}    
    for index in tqdm(indices, desc="Processing indices"):
        index_level_settings = getIndexLevelSettings(index, cluster_url)
        index_level_details = getIndexDetails(index, cluster_url)
        # put the data in json dict
        index_data[index] = {}
        # merge index_level_settings in index_data
        index_data[index].update(index_level_settings)
        # merge index_level_details in index_data
        index_data[index].update(index_level_details)        
    return index_data

"""
in this we will find index level inefficiencies in the cluster

following things will be reported
1. index replication factor is 0
2. index refresh interval is -1 or very high value
3. index number of shards is 0
4. index is not green
5. index is not open
6. index is not in active state
7. index is in read only state (this data is not available in index level settings)
8. index is in read only allow delete state (this data is not available in index level settings)

"""

def analyzeIndexLevelDetails(cluster_url="localhost:9200"):
    index_data = gatherIndexLevelData(cluster_url)
    # print(index_data)
    index_level_inefficiencies = []
    for index in index_data:
        # print(index)
        # print(index_data[index])
        # print("======================")
        temp = {}
        temp['type'] = 'index_level'
        temp['index'] = index
        
        if index_data[index]['health'] != 'green':
            # make a copy of temp and add the reason
            temp1 = temp.copy()
            temp1['message'] = "index {} is not green. Its {}".format(index,index_data[index]['health'] )
            #add callout_type
            temp1['callout_type'] = 'warning' if index_data[index]['health']=='yellow' else 'alert'
            temp1['index_health'] = index_data[index]['health']
            temp1['callout_name'] = 'index_not_green'
            index_level_inefficiencies.append(temp1)

        if index_data[index]['status'] != 'open':
            # make a copy of temp and add the reason
            temp1 = temp.copy()
            temp1['message'] = "index {} is not open".format(index)
            #add callout_type
            temp1['callout_type'] = 'warning'
            temp1['callout_name'] = 'index_not_open'
            index_level_inefficiencies.append(temp1)

        if 'number_of_replicas' in index_data[index] and int(index_data[index]['number_of_replicas']) == 0:
            # make a copy of temp and add the reason
            temp1 = temp.copy()
            temp1['message'] = "index {} has number_of_replicas 0".format(index)
            #add callout_type
            temp1['callout_type'] = 'alert'
            temp1['callout_name'] = 'index_replication_factor_zero'
            index_level_inefficiencies.append(temp1)

        if 'refresh_interval' in index_data[index] and index_data[index]['refresh_interval'] == -1:
            # make a copy of temp and add the reason
            temp1 = temp.copy()
            temp1['message'] = "index {} has refresh_interval -1. So new changes will not be searchable.".format(index)
            #add callout_type
            temp1['callout_type'] = 'alert'
            temp1['callout_name'] = 'index_refresh_interval_negative'
            index_level_inefficiencies.append(temp1)
            
    return index_level_inefficiencies
            

"""
call this api 'http://localhost:9200/_cat/shards?&format=json&pretty' to get the shard level details
[  {
    "index" : "mktorders_merged_data-480",
    "shard" : "63",
    "prirep" : "r",
    "state" : "STARTED",
    "docs" : "25238192",
    "store" : "10.2gb",
    "ip" : "10.60.54.130",
    "node" : "pawscartorderelasticsearch54130"
  },
  {
    "index" : "mktorders_merged_data-480",
    "shard" : "63",
    "prirep" : "p",
    "state" : "STARTED",
    "docs" : "25238192",
    "store" : "10.7gb",
    "ip" : "10.60.62.115",
    "node" : "pawscartorderelasticsearch62115"
  }
]
loop through all the shards and create list of shards with store size less than 10gb or greater than 50gb
"""
def getShardLevelData(cluster_url="http://localhost:9200"):
    url = "{}/_cat/shards?&format=json&pretty".format(cluster_url)
    response = requests.get(url)
    if response.status_code == 200:
        shards = response.json()
        return shards
    else:        
        return []


def analyzeShardLevelDetails(cluster_url="http://localhost:9200"):
    shards = getShardLevelData(cluster_url)
    shard_wise = []
    for shard in tqdm(shards, 'Processing shards'):        
        # check shard store does not exist
        if not shard.get('store'):
            store_size = 0
        # store size can be in mb or gb so convert them to gb and then compare. put culprit shards in array
        elif shard['store'].endswith('gb'):
            store_size = float(shard.get('store').split('gb')[0])
        elif shard['store'].endswith('mb'):
            store_size = float(shard.get('store').split('mb')[0])/1024
        elif shard['store'].endswith('kb'):
            store_size = float(shard.get('store').split('kb')[0])/(1024*1024)
        else:
            store_size = 0

        # generating recommendation for shards to be around 10 to 50 gb
        if store_size < 10:
            temp = {}
            temp['type'] = 'shard_level'
            temp['callout_name'] = 'shard_lt_10gb'
            temp['callout_type'] = 'recommendation'
            temp['index'] = shard.get('index')
            temp['shard'] = shard.get('shard')
            temp['message'] = "Index {} shard {} has store size {} which is less than 10gb".format(shard.get('index')  ,shard.get('shard'), shard.get('store'))            
            shard_wise.append(temp)
        elif store_size > 50:
            temp = {}
            temp['type'] = 'shard_level'
            temp['index'] = shard.get('index')
            temp['shard'] = shard.get('shard')
            temp['callout_name'] = 'shard_gt_50gb'
            temp['callout_type'] = 'recommendation'
            temp['message'] = "Index {} shard {} has store size {} which is greater than 50gb".format(shard.get('index')  ,shard.get('shard'), shard.get('store'))
            shard_wise.append(temp)            
    return shard_wise

"""
gets why shard is in unassigned state

curl -XGET 'localhost:9200/_cluster/allocation/explain?pretty' -H 'Content-Type: application/json' -d'{ "index": "my-index", "shard": 0, "primary": false }'

output is of the format
{
  "index" : "my_index_286",
  "shard" : 0,
  "primary" : false,
  "current_state" : "unassigned",
  "unassigned_info" : {
    "reason" : "NODE_LEFT",
    "at" : "2023-12-29T12:58:57.373Z",
    "details" : "node_left [3WRs8lY1Rb65Rn2bHgutxg]",
    "last_allocation_status" : "no_attempt"
  },
  "can_allocate" : "no",
  "allocate_explanation" : "cannot allocate because allocation is not permitted to any of the nodes",
  "node_allocation_decisions" : [
    {
      "node_id" : "Keoat0M2TdSjM_Xx_d9QOQ",
      "node_name" : "es05",
      "transport_address" : "10.89.1.37:9300",
      "node_attributes" : {
        "ml.machine_memory" : "8100388864",
        "ml.max_open_jobs" : "512",
        "xpack.installed" : "true",
        "ml.max_jvm_size" : "536870912",
        "transform.node" : "true"
      },
      "node_decision" : "no",
      "deciders" : [
        {
          "decider" : "same_shard",
          "decision" : "NO",
          "explanation" : "a copy of this shard is already allocated to this node [[my_index_286][0], node[Keoat0M2TdSjM_Xx_d9QOQ], [P], s[STARTED], a[id=wO5cg8uET_-W75wZK_uJZQ]]"
        }
      ]
    }
  ]
}
"""
def getAllocationDetailsForShard(cluster_url="http://localhost:9200", index=None, shard=None, primary=False):
    url = "{}/_cluster/allocation/explain?pretty".format(cluster_url)
    payload = {"index": index, "shard": shard}
    payload['primary'] = primary    
    response = requests.get(url, json=payload)
    if response.status_code == 200:
        return response.json()
    else:
        return {}

"""
 create a function which fetches all the shards in the cluster and then loops through them and checks if the shard is UNASSIGNED state,
if yes then call allocation explain api to get the reason why shard is in unassigned state
"""
def analyseUnassignedShards(cluster_url="http://localhost:9200"):
    shards = getShardLevelData(cluster_url)
    unassigned_shards = []
    for shard in tqdm(shards, 'Analysing unassigned shards'):
        if shard['state'] == 'UNASSIGNED':
            temp = {}
            temp['type'] = 'shard_level'
            temp['index'] = shard.get('index')
            temp['shard'] = shard.get('shard')
            temp['primary_or_replica'] = 'primary' if shard.get('prirep') == 'p' else 'replica'
            temp['callout_name'] = 'unassigned_shard'
            temp['callout_type'] = 'alert'
            temp['message'] = "Index {} shard {} is in unassigned state".format(shard.get('index')  ,shard.get('shard'))
            reason = getAllocationDetailsForShard(cluster_url, index=shard.get('index'), shard=shard.get('shard'), primary=True if shard.get('prirep') == 'p' else False)
            temp['unassigned_reason'] = reason.get('allocate_explanation')
            temp['can_allocate'] = reason.get('can_allocate')
            if ('node_allocation_decisions' in reason):
                node_based_decider = []
                for node in reason.get('node_allocation_decisions'):                    
                    if node.get('node_decision') == 'no':
                        temp_decider = {}
                        # temp_decider['node_id'] = node.get('node_id')
                        temp_decider['node_name'] = node.get('node_name')
                        temp_decider['transport_address'] = node.get('transport_address')
                        temp_decider['node_decision'] = node.get('node_decision')
                        temp_decider['deciders'] = node.get('deciders')
                        node_based_decider.append(temp_decider)
                temp['node_allocation_decisions'] = node_based_decider
            unassigned_shards.append(temp)
    return unassigned_shards


# curl to cat es nodes in verbose mode with lots of details, give the full names use the apis in https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-nodes.html
# fetch all the possible columns
# curl

"""
curl -X GET  -H 'Connection: keep-alive' -H 'User-Agent: python-requests/2.31.0' 'http://localhost:9200/_cat/nodes?v&pretty&h=*&format=json'
{
    "id" : "3-Ya",
    "pid" : "22950",
    "ip" : "10.61.5.164",
    "port" : "9300",
    "http_address" : "10.61.5.164:9200",
    "version" : "8.7.0",
    "type" : "deb",
    "build" : "09520b59b6bc1057340b55750186466ea715e30e",
    "jdk" : "19.0.2",
    "disk.total" : "99.9gb",
    "disk.used" : "3.7gb",
    "disk.avail" : "96.2gb",
    "disk.used_percent" : "3.72",
    "heap.current" : "648mb",
    "heap.percent" : "16",
    "heap.max" : "3.8gb",
    "ram.current" : "7.4gb",
    "ram.percent" : "97",
    "ram.max" : "7.6gb",
    "file_desc.current" : "822",
    "file_desc.percent" : "0",
    "file_desc.max" : "1048576",
    "cpu" : "0",
    "load_1m" : "0.00",
    "load_5m" : "0.00",
    "load_15m" : "0.00",
    "uptime" : "57.8d",
    "node.role" : "dm",
    "master" : "-",
    "name" : "sawscartorderesdummyelasticsearch5164",
    "completion.size" : "0b",
    "fielddata.memory_size" : "0b",
    "fielddata.evictions" : "0",
    "query_cache.memory_size" : "5.9mb",
    "query_cache.evictions" : "474",
    "query_cache.hit_count" : "20746",
    "query_cache.miss_count" : "28350",
    "request_cache.memory_size" : "214.2kb",
    "request_cache.evictions" : "0",
    "request_cache.hit_count" : "744",
    "request_cache.miss_count" : "1893",
    "flush.total" : "5216",
    "flush.total_time" : "23.1m",
    "get.current" : "0",
    "get.time" : "22.7s",
    "get.total" : "266438",
    "get.exists_time" : "18.8s",
    "get.exists_total" : "182814",
    "get.missing_time" : "3.9s",
    "get.missing_total" : "83624",
    "indexing.delete_current" : "0",
    "indexing.delete_time" : "0s",
    "indexing.delete_total" : "0",
    "indexing.index_current" : "0",
    "indexing.index_time" : "3.5h",
    "indexing.index_total" : "92200595",
    "indexing.index_failed" : "3628",
    "merges.current" : "0",
    "merges.current_docs" : "0",
    "merges.current_size" : "0b",
    "merges.total" : "3716",
    "merges.total_docs" : "92032153",
    "merges.total_size" : "23.6gb",
    "merges.total_time" : "54.4m",
    "refresh.total" : "50301",
    "refresh.time" : "27.6m",
    "refresh.external_total" : "41999",
    "refresh.external_time" : "19m",
    "refresh.listeners" : "0",
    "script.compilations" : "1",
    "script.cache_evictions" : "0",
    "script.compilation_limit_triggered" : "0",
    "search.fetch_current" : "0",
    "search.fetch_time" : "2.6s",
    "search.fetch_total" : "10165",
    "search.open_contexts" : "0",
    "search.query_current" : "0",
    "search.query_time" : "22.9s",
    "search.query_total" : "18885",
    "search.scroll_current" : "0",
    "search.scroll_time" : "0s",
    "search.scroll_total" : "0",
    "segments.count" : "542",
    "segments.memory" : "0b",
    "segments.index_writer_memory" : "0b",
    "segments.version_map_memory" : "0b",
    "segments.fixed_bitset_memory" : "0b",
    "suggest.current" : "0",
    "suggest.time" : "0s",
    "suggest.total" : "0",
    "bulk.total_operations" : "358019",
    "bulk.total_time" : "3.8h",
    "bulk.total_size_in_bytes" : "101323131784",
    "bulk.avg_time" : "0s",
    "bulk.avg_size_in_bytes" : "214484",
    "shard_stats.total_count" : "108",
    "mappings.total_count" : "7821",
    "mappings.total_estimated_overhead_in_bytes" : "7.6mb"
  }
"""
def getAllNodeLevelDetails(cluster_url="http://localhost:9200"):
    url = "{}/_cat/nodes?v&h=*&format=json".format(cluster_url)
    response = requests.get(url)
    if response.status_code == 200:
        # print(to_curl(response.request))
        return response.json()
    else:
        return {}

"""
{    "heap.current" : "648mb",
    "heap.percent" : "16",
    "heap.max" : "3.8gb",
    "ram.current" : "7.4gb",
    "ram.percent" : "97",
    "ram.max" : "7.6gb",
}
given above fields in an object, find the ram.max and heap.max and return the percentage of ram.max and heap.max handling gb and mb separately
"""
def heapAllocationPercentage(heap):
    # if heap.get(heap.max).endswith("gb"): then handle it differently else handle it differently
    # convert both heap.max and ram.max to mb and then find the percentage
    # heap.max/ram.max * 100

    if heap.get('heap.max').endswith("gb"):
        heap_max = float(heap.get('heap.max').replace("gb","")) * 1024
    else:
        heap_max = float(heap.get('heap.max').replace("mb",""))

    if heap.get('ram.max').endswith("gb"):
        ram_max = float(heap.get('ram.max').replace("gb","")) * 1024
    else:
        ram_max = float(heap.get('ram.max').replace("mb",""))

    return (heap_max/ram_max) * 100
            
        

    
def analyzeAllNodeLevelDetails(cluster_url="http://localhost:9200"):
    nodes = getAllNodeLevelDetails(cluster_url)
    total_indices = getAllIndices(cluster_url)

    node_data = []
    for node in tqdm(nodes, desc="Analyzing nodes"):
        # identify what to analyse at node level
        heap_percent = heapAllocationPercentage(node)
        if(heap_percent < 40):
            temp_obj = {}
            temp_obj['type'] = 'node_level'
            temp_obj['value'] = heap_percent
            temp_obj['heap'] = node.get('heap.max')
            temp_obj['ram'] = node.get('ram.max')
            temp_obj['callout_type'] = 'warning'
            temp_obj['callout_name'] = 'heap_percent_less_than_40'
            # get http_address
            temp_obj['http_address'] = node.get('http_address')
            # type a message
            temp_obj['message'] = "heap percent is less than 40% on node {} with heap {} and ram {}".format(node.get('http_address'), node.get('heap.max'), node.get('ram.max'))
            # add to node_data
            # add temp_obj to node_data
            node_data.append(temp_obj)

        # if node is master then check the total number of indices in cluster and if it is more than 3000 then callout and push it in node_data, node.role will have values like dm , m , d etc
        # check if node is master by checking if node.role has m in string or not
        if 'm' in node.get('node.role'):
            # extract heap max of node
            if node.get('heap.max').endswith("gb"):
                heap_max = float(node.get('heap.max').replace("gb","")) 
            else:
                heap_max = float(node.get('heap.max').replace("mb",""))/1024
            total_allowed_indices = heap_max * 3000
            
            if len(total_indices) > total_allowed_indices:
                temp_obj = {}
                temp_obj['type'] = 'cluster_level'
                temp_obj['value'] = node.get('indices.count')
                temp_obj['callout_type'] = 'warning'
                temp_obj['callout_name'] = 'indices_count_more_than_3000_per_1gb_master_node'
                # get http_address
                temp_obj['http_address'] = node.get('http_address')
                # type a message
                temp_obj['message'] = "indices count is {} while cluster can safely support {} total indices".format(len(total_indices),total_allowed_indices )
                temp_obj['reference'] = "https://www.elastic.co/guide/en/elasticsearch/reference/current/size-your-shards.html"
                # add to node_data
                node_data.append(temp_obj)
                
    return node_data


"""
curl -X GET  -H 'Connection: keep-alive' -H 'User-Agent: python-requests/2.31.0' 'http://localhost:9200/_cluster/stats?pretty'

{
  "_nodes" : {
    "total" : 5,
    "successful" : 5,
    "failed" : 0
  },
  "cluster_name" : "es-docker-cluster",
  "cluster_uuid" : "wUrfObFwQlC0bdO16V2Rkg",
  "timestamp" : 1703858969254,
  "status" : "red",
  "indices" : {
    "count" : 0,
    "shards" : { },
    "docs" : {
      "count" : 0,
      "deleted" : 0
    },
    "store" : {
      "size_in_bytes" : 0,
      "total_data_set_size_in_bytes" : 0,
      "reserved_in_bytes" : 0
    },
    "fielddata" : {
      "memory_size_in_bytes" : 0,
      "evictions" : 0
    },
    "query_cache" : {
      "memory_size_in_bytes" : 0,
      "total_count" : 0,
      "hit_count" : 0,
      "miss_count" : 0,
      "cache_size" : 0,
      "cache_count" : 0,
      "evictions" : 0
    },
    "completion" : {
      "size_in_bytes" : 0
    },
    "segments" : {
      "count" : 0,
      "memory_in_bytes" : 0,
      "terms_memory_in_bytes" : 0,
      "stored_fields_memory_in_bytes" : 0,
      "term_vectors_memory_in_bytes" : 0,
      "norms_memory_in_bytes" : 0,
      "points_memory_in_bytes" : 0,
      "doc_values_memory_in_bytes" : 0,
      "index_writer_memory_in_bytes" : 0,
      "version_map_memory_in_bytes" : 0,
      "fixed_bit_set_memory_in_bytes" : 0,
      "max_unsafe_auto_id_timestamp" : -9223372036854775808,
      "file_sizes" : { }
    },
    "mappings" : {
      "field_types" : [
        {
          "name" : "boolean",
          "count" : 1,
          "index_count" : 1,
          "script_count" : 0
        },
        {
          "name" : "constant_keyword",
          "count" : 3,
          "index_count" : 1,
          "script_count" : 0
        },
        {
          "name" : "date",
          "count" : 6,
          "index_count" : 2,
          "script_count" : 0
        },
        {
          "name" : "ip",
          "count" : 1,
          "index_count" : 1,
          "script_count" : 0
        },
        {
          "name" : "keyword",
          "count" : 1195,
          "index_count" : 394,
          "script_count" : 0
        },
        {
          "name" : "long",
          "count" : 1,
          "index_count" : 1,
          "script_count" : 0
        },
        {
          "name" : "object",
          "count" : 13,
          "index_count" : 2,
          "script_count" : 0
        },
        {
          "name" : "text",
          "count" : 1180,
          "index_count" : 394,
          "script_count" : 0
        }
      ],
      "runtime_field_types" : [ ]
    },
    "analysis" : {
      "char_filter_types" : [ ],
      "tokenizer_types" : [ ],
      "filter_types" : [ ],
      "analyzer_types" : [ ],
      "built_in_char_filters" : [ ],
      "built_in_tokenizers" : [ ],
      "built_in_filters" : [ ],
      "built_in_analyzers" : [ ]
    },
    "versions" : [
      {
        "version" : "7.17.8",
        "index_count" : 394,
        "primary_shard_count" : 394,
        "total_primary_bytes" : 0
      }
    ]
  },
  "nodes" : {
    "count" : {
      "total" : 5,
      "coordinating_only" : 0,
      "data" : 2,
      "data_cold" : 2,
      "data_content" : 2,
      "data_frozen" : 2,
      "data_hot" : 2,
      "data_warm" : 2,
      "ingest" : 5,
      "master" : 3,
      "ml" : 5,
      "remote_cluster_client" : 5,
      "transform" : 2,
      "voting_only" : 0
    },
    "versions" : [
      "7.17.8"
    ],
    "os" : {
      "available_processors" : 20,
      "allocated_processors" : 20,
      "names" : [
        {
          "name" : "Linux",
          "count" : 5
        }
      ],
      "pretty_names" : [
        {
          "pretty_name" : "Ubuntu 20.04.5 LTS",
          "count" : 5
        }
      ],
      "architectures" : [
        {
          "arch" : "aarch64",
          "count" : 5
        }
      ],
      "mem" : {
        "total_in_bytes" : 40501944320,
        "free_in_bytes" : 3302400000,
        "used_in_bytes" : 37199544320,
        "free_percent" : 8,
        "used_percent" : 92
      }
    },
    "process" : {
      "cpu" : {
        "percent" : 0
      },
      "open_file_descriptors" : {
        "min" : 377,
        "max" : 381,
        "avg" : 378
      }
    },
    "jvm" : {
      "max_uptime_in_millis" : 4445156,
      "versions" : [
        {
          "version" : "19.0.1",
          "vm_name" : "OpenJDK 64-Bit Server VM",
          "vm_version" : "19.0.1+10-21",
          "vm_vendor" : "Oracle Corporation",
          "bundled_jdk" : true,
          "using_bundled_jdk" : true,
          "count" : 5
        }
      ],
      "mem" : {
        "heap_used_in_bytes" : 1420014480,
        "heap_max_in_bytes" : 2684354560
      },
      "threads" : 161
    },
    "fs" : {
      "total_in_bytes" : 104857600,
      "free_in_bytes" : 104226816,
      "available_in_bytes" : 104226816
    },
    "plugins" : [ ],
    "network_types" : {
      "transport_types" : {
        "security4" : 5
      },
      "http_types" : {
        "security4" : 5
      }
    },
    "discovery_types" : {
      "zen" : 5
    },
    "packaging_types" : [
      {
        "flavor" : "default",
        "type" : "docker",
        "count" : 5
      }
    ],
    "ingest" : {
      "number_of_pipelines" : 2,
      "processor_stats" : {
        "gsub" : {
          "count" : 0,
          "failed" : 0,
          "current" : 0,
          "time_in_millis" : 0
        },
        "script" : {
          "count" : 0,
          "failed" : 0,
          "current" : 0,
          "time_in_millis" : 0
        }
      }
    }
  }
}
"""
# get cluster level details
def getClusterLevelStats(cluster_url="http://localhost:9200"):
    url = "{}/_cluster/stats?pretty".format(cluster_url)
    response = requests.get(url)
    if response.status_code == 200:
        # print(to_curl(response.request))
        return response.json()
    else:
        return {}

def getClusterLevelSettings(cluster_url="http://localhost:9200"):
    url = "{}/_cluster/settings?include_defaults=true&pretty&flat_settings".format(cluster_url)
    response = requests.get(url)
    if response.status_code == 200:
        # print(to_curl(response.request))
        return response.json()
    else:
        return {}

"""
get cluster health

"""

def getClusterHealth(cluster_url="http://localhost:9200"):
    url = "{}/_cluster/health?pretty".format(cluster_url)
    response = requests.get(url)
    if response.status_code == 200:
        # print(to_curl(response.request))
        return response.json()
    else:
        return {}

def extractValueAndUnitInMb(value):
    # if value is undefined then return 0
    # AttributeError: 'NoneType' object has no attribute 'endswith'    
    if value is None:
        return None
    if value.endswith("gb"):
        return float(value.replace("gb","")) * 1024
    elif value.endswith("tb"):
        return float(value.replace("tb","")) * 1024 * 1024
    elif value.endswith("kb"):
        return float(value.replace("kb","")) / 1024
    else:
        return float(value.replace("mb",""))
    
def analyzeClusterLevelDetails(cluster_url="http://localhost:9200"):
    cluster_stats = getClusterLevelStats(cluster_url)
    cluster_settings = getClusterLevelSettings(cluster_url)
    cluster_health = getClusterHealth(cluster_url)
    # print(cluster_stats)
    cluster_data = []
    # identify what to analyse at cluster level
    if(cluster_health.get('number_of_data_nodes') < 2):
        temp_obj = {}
        temp_obj['type'] = 'cluster_level'
        temp_obj['value'] = cluster_health.get('number_of_data_nodes')
        temp_obj['callout_type'] = 'warning'
        temp_obj['callout_name'] = 'number_of_data_nodes_less_than_2'
        # type a message
        temp_obj['message'] = "number of data nodes is less than 2. There are {} data nodes".format(cluster_health.get('number_of_data_nodes'))
        # add to node_data
        cluster_data.append(temp_obj)


    if(cluster_settings.get('persistent').get('cluster.routing.allocation.enable') == 'none' or cluster_settings.get('transient').get('cluster.routing.allocation.enable') == 'none'):
        temp_obj = {}
        temp_obj['type'] = 'cluster_level'
        temp_obj['value'] = cluster_settings.get('persistent').get('cluster.routing.allocation.enable')
        temp_obj['callout_type'] = 'warning'
        temp_obj['callout_name'] = 'cluster_routing_allocation_enable_none'
        # type a message
        temp_obj['message'] = "cluster.routing.allocation.enable is none. If any es node goes down, shards will not automatically relocate. It should be all"
        # add to node_data
        cluster_data.append(temp_obj)

    # check if max index transfer speed is more than 40mbps
    if('indices.recovery.max_bytes_per_sec' in cluster_settings.get('persistent') or 'indices.recovery.max_bytes_per_sec' in cluster_settings.get('transient')):
        #extract the value in mb from the string
        value_persistent = cluster_settings.get('persistent').get('indices.recovery.max_bytes_per_sec')
        value_transient = cluster_settings.get('transient').get('indices.recovery.max_bytes_per_sec')
        speed_persistent = None
        speed_transient = None
        if value_persistent is not None:
            speed_persistent = extractValueAndUnitInMb(value_persistent)
        if value_transient is not None:
            speed_transient = extractValueAndUnitInMb(value_transient)

        if (speed_persistent is not None and speed_persistent > 40) or (speed_transient is not None and speed_transient > 40):
            temp_obj = {}
            temp_obj['type'] = 'cluster_level'
            temp_obj['value'] = speed_persistent if speed_persistent is not None else speed_transient
            temp_obj['callout_type'] = 'warning'
            temp_obj['callout_name'] = 'indices_recovery_max_bytes_per_sec'
            # type a message
            temp_obj['message'] = "indices.recovery.max_bytes_per_sec is {} mbps or {} mbps. It is recommended to keep it below 40mbps".format(speed_persistent if speed_persistent is not None else "", speed_transient if speed_transient is not None else "")
            # add to node_data
            cluster_data.append(temp_obj)
        
    return cluster_data
    


def generate_html_report(all_level_data):
    html = """
    <html>
    <head>
        <title>ES Health Check</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .level, .category, .issue { margin-left: 20px; }
            .toggle { cursor: pointer; user-select: none; }
            .toggle::before { content: '▶ '; }
            .toggle.open::before { content: '▼ '; }
            .content { display: none; }
            .content.show { display: block; }
            .issue { border: 1px solid #ddd; padding: 10px; margin-bottom: 10px; }
            .warning { background-color: #fff3cd; }
            .alert { background-color: #f8d7da; }
            .recommendation { background-color: #d4edda; }
            .occurrence { margin-top: 10px; padding-left: 20px; border-left: 3px solid #007bff; }
        </style>
        <script>
            function toggle(el) {
                el.classList.toggle('open');
                el.nextElementSibling.classList.toggle('show');
            }
        </script>
    </head>
    <body>
        <h1>Elasticsearch Health Check Report</h1>
    """

    for level, issues in all_level_data.items():
        if issues:
            html += f"<div class='level'>"
            html += f"<h2 class='toggle' onclick='toggle(this)'>{level.replace('_', ' ').title()}</h2>"
            html += f"<div class='content'>"
            
            categories = {}
            for issue in issues:
                category = issue.get('callout_name', 'Other')
                if category not in categories:
                    categories[category] = []
                categories[category].append(issue)
            
            for category, category_issues in categories.items():
                html += f"<div class='category'>"
                html += f"<h3 class='toggle' onclick='toggle(this)'>{category.replace('_', ' ').title()} ({len(category_issues)})</h3>"
                html += f"<div class='content'>"
                
                unique_messages = {}
                for issue in category_issues:
                    message = issue.get('message', '')
                    if message not in unique_messages:
                        unique_messages[message] = []
                    unique_messages[message].append(issue)
                
                for message, occurrences in unique_messages.items():
                    html += f"<div class='issue {occurrences[0].get('callout_type', '')}'>"
                    html += f"<p><strong>Message:</strong> {message}</p>"
                    html += f"<p><strong>Occurrences:</strong> {len(occurrences)}</p>"
                    html += f"<div class='toggle' onclick='toggle(this)'>Show Details</div>"
                    html += f"<div class='content'>"
                    for occurrence in occurrences:
                        html += f"<div class='occurrence'>"
                        for key, value in occurrence.items():
                            if key not in ['message', 'callout_type', 'callout_name']:
                                html += f"<p><strong>{key}:</strong> {value}</p>"
                        html += "</div>"
                    html += "</div>"
                    html += "</div>"
                
                html += "</div></div>"
            
            html += "</div></div>"

    html += """
    </body>
    </html>
    """
    return html

# print(gatherIndexLevelData(args.cluster_url))
# print(getIndexLevelSettings('mktorders-10005', args.cluster_url))
# print(getIndexDetails('mktorders-10005', args.cluster_url))

# print(getAllNodeLevelDetails(args.cluster_url))

# keep appending recommmendations from all analyzers into an array

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cluster_url", help="provide cluster url")
    args = parser.parse_args()

    logging.info(f"Starting ES health check for cluster: {args.cluster_url}")

    with tqdm(total=5, desc="Overall Progress") as pbar:
        node_level = analyzeAllNodeLevelDetails(args.cluster_url)
        pbar.update(1)

        shard_level = analyzeShardLevelDetails(args.cluster_url)
        pbar.update(1)

        cluster_level = analyzeClusterLevelDetails(args.cluster_url)
        pbar.update(1)

        index_level = analyzeIndexLevelDetails(args.cluster_url)
        pbar.update(1)

        unassigned_shard_data = analyseUnassignedShards(args.cluster_url)
        pbar.update(1)

    all_level_data = {
        'node_level': node_level,
        'shard_level': shard_level,
        'cluster_level': cluster_level,
        'index_level': index_level,
        'unassigned_shard_data': unassigned_shard_data
    }

    logging.info("Generating HTML report...")
    html_str = generate_html_report(all_level_data)

    with open("es_health_check.html", "w") as f:
        f.write(html_str)

    logging.info("ES health check completed. Report saved as es_health_check.html")

if __name__ == "__main__":
    main()

# print(analyzeIndexLevelData(args.cluster_url))

# pretty print the response of cluster level details
# print(json.dumps(getClusterLevelDetails(args.cluster_url), indent=4, sort_keys=True))

# print(heapAllocationPercentage({    "heap.current" : "648mb",    "heap.percent" : "16",    "heap.max" : "3.8gb",    "ram.current" : "7.4gb",    "ram.percent" : "97",    "ram.max" : "7.6gb"}))


#curl to print default cluster settings in elasticsearch
# curl -X GET "localhost:9200/_cluster/settings?include_defaults=true&pretty"
