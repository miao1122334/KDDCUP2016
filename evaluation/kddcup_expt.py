'''
Created on Mar 13, 2016

@author: hugo
'''
from mymysql.mymysql import MyMySQL
import config
from collections import defaultdict
import time

# import logging as log
import os
import cPickle
# from baselines.scholar import match_by_title
from evaluation.metrics import ndcg2
from datasets.mag import get_selected_docs
from ranking.kddcup_searchers import simple_search, SimpleSearcher, Searcher


# log.basicConfig(format='%(asctime)s [%(levelname)s] : %(message)s', level=log.INFO)

db = MyMySQL(db=config.DB_NAME, user=config.DB_USER, passwd=config.DB_PASSWD)


def get_affil_based_on_id(affil_ids):
    affil_names = []
    for each in affil_ids:
        affil_name = db.select("name", "affils", where="id='%s'"%each, limit=1)[0]
        affil_names.append(affil_name)

    return affil_names

def calc_ground_truth_score(selected_affils, conf_name, year="2015"): # {paper_id: {author_id:[affil_id,],},}
    """
    Uses latest pub records to estimate ground truth scores.
    """
    ground_truth = simple_search(selected_affils, conf_name, year, age_decay=False)

    return ground_truth


def get_results_file(conf_name, method_name) :
    folder = "%sresults/%s" % (config.DATA, conf_name)
    if not os.path.exists(folder) :
        os.makedirs(folder)

    return "%s/%s.tsv" % (folder, method_name)


def save_results(conf_id, results, file_path) :
    '''
    Saves the results in a output file.
    '''
    # cPickle.dump(results, open(file_path, 'w'))
    # write to tsv file
    try:
        f = open(file_path, 'w+')
    except Exception, e:
        print e
        return

    for affil_id, score in results:
        # [conference id] \t [affiliation id] \t [probability score] \n
        f.writelines("%s\t%s\t%s\n"%(conf_id, affil_id, score))
    f.close()


def get_search_metrics(selected_affils, ground_truth, conf_name, year, searcher, exclude_papers=[], show=True, results_file=None) :
    '''
    Run searches on each conference (conference -> ground truth) and return
    the evaluate metric for each instance. Right now the metrics being
    returned is NDCG.

    Returns: dict {metric: value}
    '''
    metrics = defaultdict(list)
    conf_id = db.select("id", "confs", where="abbr_name='%s'"%conf_name, limit=1)[0]
    start = time.time()

    if searcher.name() == "SimpleSearcher":
        # expand_year = []
        expand_year = range(2005, 2011)
        results = searcher.search(selected_affils, conf_name, year, expand_year=expand_year, age_decay=True, rtype="affil")
    else:
        results = searcher.search(selected_affils, conf_name, year, exclude_papers, force=True, rtype="affil")

    metrics["Time"] = time.time() - start

    actual, relevs = zip(*ground_truth)
    pred = zip(*results)[0]

    # actual_affils = get_affil_based_on_id(actual)
    # ground_5y = simple_search(selected_affils, conf_name, [2011,2012,2013,2014,2015], age_decay=False)
    # ground_5y_affils = get_affil_based_on_id(zip(*ground_5y)[0])
    # import pdb;pdb.set_trace()
    # ground_4y = simple_search(selected_affils, conf_name, [2011,2012,2013,2014], age_decay=False)
    # ground_4y_affils = get_affil_based_on_id(zip(*ground_4y)[0])

    # pred_affils = get_affil_based_on_id(pred)
    # print "actual affils"
    # print actual_affils[:20]
    # print "pred affils"
    # print pred_affils[:20]
    # print "pred scores"
    # print zip(*results)[1][:20]

    # import pdb;pdb.set_trace()
    metrics["NDCG"] = ndcg2(actual, pred, relevs, k=20)


    if results_file:
        save_results(conf_id, results, results_file)

    if show:
        for k, v in metrics.iteritems():
            print u"%s: %f\t" % (k, v)
        print

    return metrics

def main():

    confs = [
                "SIGIR", # Phase 1
                # "SIGMOD",
                # "SIGCOMM",

                # "KDD", # Phase 2
                # "ICML",

                # "FSE", # Phase 3
                # "MobiCom",
                # "MM",
            ]

    searchers = [
                    # SimpleSearcher(**config.PARAMS),
                    Searcher(**config.PARAMS),

                ]

    # import pdb;pdb.set_trace()
    selected_affils = db.select(fields="id", table="selected_affils")
    year = ["2011", "2012", "2013", "2014"]
    for c in confs :
        # log.info("Running '%s' conf.\n" % c)
        print "Running on '%s' conf." % c
        ground_truth = calc_ground_truth_score(selected_affils, c) # low coverage
        # count = 0
        # for k, v in ground_truth:
        #     if v == 0:
        #         count += 1
        # print "%s/%s"%(count, len(ground_truth))
        exclude_papers = zip(*get_selected_docs(c, "2015"))[0]

        for s in searchers :
            print "Running %s." % s.name()

            if s.name() == "SimpleSearcher":
                s.set_params(**{
                              'age_relev': .5, # .5, .7, .08
                              })

            if s.name() == "MultiLayered":
                s.set_params(**{
                              'H': 0,
                              'age_relev': 0.01, # 0.01
                              'papers_relev': .99, # .99
                              'authors_relev': .01, # .01
                              # 'words_relev': .2,
                              # 'venues_relev' : .2,
                              'author_affils_relev': .95, # .95, .99, .99
                              'alpha': 0.01}) # .01, .35, .25

            rfile = get_results_file(c, s.name())
            get_search_metrics(selected_affils, ground_truth, c, year, s,\
                         exclude_papers=exclude_papers, results_file=rfile)
            del s
        print


if __name__ == "__main__":
    main()
