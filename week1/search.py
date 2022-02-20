#
# The main search hooks for the Search Flask application.
#
from flask import (
    Blueprint, redirect, render_template, request, url_for
)

from week1.opensearch import get_opensearch

bp = Blueprint('search', __name__, url_prefix='/search')


# Process the filters requested by the user and return a tuple that is appropriate for use in: the query, URLs displaying the filter and the display of the applied filters
# filters -- convert the URL GET structure into an OpenSearch filter query
# display_filters -- return an array of filters that are applied that is appropriate for display
# applied_filters -- return a String that is appropriate for inclusion in a URL as part of a query string.  This is basically the same as the input query string
def process_filters(filters_input):
    # Filters look like: &filter.name=regularPrice&regularPrice.key={{ agg.key }}&regularPrice.from={{ agg.from }}&regularPrice.to={{ agg.to }}
    filters = []
    display_filters = []  
    applied_filters = ""

    for filter in filters_input:
        type = request.args.get(filter + ".type")
        display_name = request.args.get(filter + ".displayName", filter)
        
        # We need to capture and return what filters are already applied so they can be automatically added to any existing links we display in aggregations.jinja2
        applied_filters += "&filter.name={}&{}.type={}&{}.displayName={}".format(filter, filter, type, filter,
                                                                                 display_name)
        display_filters.append(display_name)
        # filters get used in create_query below.  display_filters gets used by display_filters.jinja2 and applied_filters gets used by aggregations.jinja2 (and any other links that would execute a search.)
        if type == "range":
            from_val = request.args.get(filter + ".from")
            to_val = request.args.get(filter + ".to")
            range_filter = {}

            if from_val:
                range_filter["gte"] = from_val
            if to_val:
                range_filter["lte"] = to_val

            the_filter = {"range": {filter: range_filter}}
            filters.append(the_filter)
            display_filters.append("{}: from={} to={}".format(display_name, from_val, to_val))
            applied_filters += "&{}.from={}&{}.to={}".format(filter, from_val, filter, to_val)

        elif type == "terms":
            field = request.args.get(filter + ".fieldName", filter)
            key = request.args.get(filter + ".key")
            the_filter = {"term": {field: key}}
            filters.append(the_filter)
            display_filters.append("{}: {}".format(display_name, key))
            applied_filters += "&{}.fieldName={}&{}.key={}".format(filter, field, filter, key)

    print("Filters: {}".format(filters))

    return filters, display_filters, applied_filters

# Our main query route.  Accepts POST (via the Search box) and GETs via the clicks on aggregations/facets
@bp.route('/query', methods=['GET', 'POST'])
def query():
    opensearch = get_opensearch() # Load up our OpenSearch client from the opensearch.py file.
    # Put in your code to query opensearch.  Set error as appropriate.
    error = None
    user_query = None
    query_obj = None
    display_filters = None
    applied_filters = ""
    filters = None
    sort = "_score"
    sortDir = "desc"

    # a query has been submitted
    if request.method == 'POST':  
        user_query = request.form['query']
        if not user_query:
            user_query = "*"
        sort = request.form["sort"]
        if not sort:
            sort = "_score"
        sortDir = request.form["sortDir"]
        if not sortDir:
            sortDir = "desc"
        query_obj = create_query(user_query, [], sort, sortDir)

    # Handle the case where there is no query or just loading the page    
    elif request.method == 'GET':  
        user_query = request.args.get("query", "*")
        filters_input = request.args.getlist("filter.name")
        sort = request.args.get("sort", sort)
        sortDir = request.args.get("sortDir", sortDir)
        if filters_input:
            (filters, display_filters, applied_filters) = process_filters(filters_input)

        query_obj = create_query(user_query, filters, sort, sortDir)
    else:
        query_obj = create_query("*", [], sort, sortDir)
    
    # Search opensearch index for given query 
    print("query obj: {}".format(query_obj))
    response = opensearch.search(body=query_obj, index="bbuy_products")

    if error is None:
        return render_template("search_results.jinja2", query=user_query, search_response=response,
                               display_filters=display_filters, applied_filters=applied_filters,
                               sort=sort, sortDir=sortDir)
    else:
        redirect(url_for("index"))


def create_query(user_query, filters, sort="_score", sortDir="desc"):
    print("Query: {} Filters: {} Sort: {}".format(user_query, filters, sort))

    search_query = {
        "query_string": {
            "query": user_query,
            "fields": ["name^1000", "shortDescription^50", "longDescription^10", "department"]
        }
    }

    must_queries = [search_query]

    if filters is not None:
        must_queries.extend(filters)

    query_obj = {
        "_source": [
            "productId", 
            "name", 
            "shortDescription", 
            "longDescription",
            "department",
            "salesRankShortTerm",  
            "salesRankMediumTerm", 
            "salesRankLongTerm",
            "regularPrice",
            "categoryPath"
        ],
        'size': 10,
        "sort": [
            {
                sort: {
                    "order": sortDir
                }
            }
        ],
        "query": {
            "function_score": {
                "query": {
                    "bool": {
                        "must": must_queries
                    }
                },
                "boost_mode": "multiply",
                "score_mode": "avg",
                "functions": [
                    {
                        "field_value_factor": {
                            "field": "salesRankLongTerm",
                            "factor": 1.3,
                            "modifier": "reciprocal",
                            "missing": 100000000
                        }
                    },
                    {
                        "field_value_factor": {
                            "field": "salesRankMediumTerm",
                            "factor": 1.2,
                            "modifier": "reciprocal",
                            "missing": 100000000
                        }
                    },
                    {
                        "field_value_factor": {
                            "field": "salesRankShortTerm",
                            "factor": 1.1,
                            "modifier": "reciprocal",
                            "missing": 100000000
                        }
                    }
                ]
            }
        },
        "aggs": {
            "department": {
                "terms": {
                    "field": "department",
                    "min_doc_count": 1
                }
            },
            "missing_images": {
                "missing": {
                    "field": "image"
                }
            },
            "regularPrice": {
                "range": {
                    "field": "regularPrice",
                    "ranges": [
                        {"key": "$", "from": 0, "to": 100},
                        {"key": "$$", "from": 100, "to": 200},
                        {"key": "$$$", "from": 200, "to": 300},
                        {"key": "$$$$", "from": 300, "to": 400},
                        {"key": "$$$$$", "from": 400, "to": 500},
                        {"key": "$$$$$$", "from": 500},
                    ]
                },
                "aggs": {
                    "price_stats": {
                        "stats": {"field": "regularPrice"}
                    }
                }
            }
        }
    }
    return query_obj
