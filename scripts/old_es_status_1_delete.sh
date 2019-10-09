#finds the exinsting status 1 docs
#deletes the documents by query
#then check if count is 0 for status 1 items
#the force_merge or optimize the index for expunging deletes as disk is released after merge
#for indices where there are no deletes we have to merge forcefully
echo "curl -H \"Content-Type: application/json\" -XGET localhost:9200/$1/_count?pretty -d '{\"query\":{\"filtered\":{\"filter\":{\"bool\":{\"must\":[{\"terms\":{\"payment_status\":[4]}},{\"range\":{\"created_at\":{\"lt\":\"now-6M\"}}}]}}}}}'"
echo "curl -H \"Content-Type: application/json\" -XDELETE localhost:9200/$1/_query?pretty -d '{\"query\":{\"filtered\":{\"filter\":{\"bool\":{\"must\":[{\"terms\":{\"payment_status\":[4]}},{\"range\":{\"created_at\":{\"lt\":\"now-6M\"}}}]}}}}}'"
echo "curl -H \"Content-Type: application/json\" -XGET localhost:9200/$1/_count?pretty -d '{\"query\":{\"filtered\":{\"filter\":{\"bool\":{\"must\":[{\"terms\":{\"payment_status\":[4]}},{\"range\":{\"created_at\":{\"lt\":\"now-6M\"}}}]}}}}}'"
echo "curl -XPOST 'http://localhost:9200/$1/_optimize?only_expunge_deletes=true' &"
