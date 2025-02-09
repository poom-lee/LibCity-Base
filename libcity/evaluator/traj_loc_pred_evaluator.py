import os
import json
import time

from libcity.evaluator.abstract_evaluator import AbstractEvaluator
from libcity.evaluator.eval_funcs import top_k
from logging import getLogger
allowed_metrics = ['Precision', 'Recall', 'F1', 'MRR', 'MAP', 'NDCG']


class TrajLocPredEvaluator(AbstractEvaluator):

    def __init__(self, config):
        self.metrics = config['metrics']  # 评估指标, 是一个 list
        self.config = config
        self.topk = config['topk']
        self.result = {}
        # 兼容全样本评估与负样本评估
        self.evaluate_method = config['evaluate_method']
        self.intermediate_result = {
            'total': 0,
            'hit': 0,
            'rank': 0.0,
            'dcg': 0.0
        }
        self._check_config()
        self._logger = getLogger()

    def _check_config(self):
        if not isinstance(self.metrics, list):
            raise TypeError('Evaluator type is not list')
        for i in self.metrics:
            if i not in allowed_metrics:
                raise ValueError('the metric is not allowed in \
                    TrajLocPredEvaluator')

    def collect(self, batch):
        """
        Args:
            batch (dict): contains three keys: uid, loc_true, and loc_pred.
            uid (list): 来自于 batch 中的 uid，通过索引可以确定 loc_true 与 loc_pred
                中每一行（元素）是哪个用户的一次输入。
            loc_true (list): 期望地点(target)，来自于 batch 中的 target。
                对于负样本评估，loc_pred 中第一个点是 target 的置信度，后面的都是负样本的
            loc_pred (matrix): 实际上模型的输出，batch_size * output_dim.
        """
        if not isinstance(batch, dict):
            raise TypeError('evaluator.collect input is not a dict of user')
        hit, rank, dcg = top_k(batch['loc_pred'], batch['loc_true'], self.topk)
        total = len(batch['loc_true'])
        self.intermediate_result['total'] += total
        self.intermediate_result['hit'] += hit
        self.intermediate_result['rank'] += rank
        self.intermediate_result['dcg'] += dcg

    def evaluate(self):
        precision_key = 'Precision@{}'.format(self.topk)
        precision = self.intermediate_result['hit'] / (
            self.intermediate_result['total'] * self.topk)
        if 'Precision' in self.metrics:
            self.result[precision_key] = precision
        # recall is used to valid in the trainning, so must exit
        recall_key = 'Recall@{}'.format(self.topk)
        recall = self.intermediate_result['hit'] \
            / self.intermediate_result['total']
        self.result[recall_key] = recall
        if 'F1' in self.metrics:
            f1_key = 'F1@{}'.format(self.topk)
            if precision + recall == 0:
                self.result[f1_key] = 0.0
            else:
                self.result[f1_key] = (2 * precision * recall) / (precision +
                                                                  recall)
        if 'MRR' in self.metrics:
            mrr_key = 'MRR@{}'.format(self.topk)
            self.result[mrr_key] = self.intermediate_result['rank'] \
                / self.intermediate_result['total']
        if 'MAP' in self.metrics:
            map_key = 'MAP@{}'.format(self.topk)
            self.result[map_key] = self.intermediate_result['rank'] \
                / self.intermediate_result['total']
        if 'NDCG' in self.metrics:
            ndcg_key = 'NDCG@{}'.format(self.topk)
            self.result[ndcg_key] = self.intermediate_result['dcg'] \
                / self.intermediate_result['total']
        return self.result

    def save_result(self, save_path, filename=None):
        self.evaluate()
        if not os.path.exists(save_path):
            os.mkdir(save_path)
        if filename is None:
            # 使用时间戳
            filename = time.strftime(
                "%Y_%m_%d_%H_%M_%S", time.localtime(time.time()))
        self._logger.info('evaluate result is ', json.dumps(self.result, indent=1))
        with open(os.path.join(save_path, '{}.json'.format(filename)), 'w') \
                as f:
            json.dump(self.result, f)

    def clear(self):
        self.result = {}
        self.intermediate_result = {
            'total': 0,
            'hit': 0,
            'rank': 0.0,
            'dcg': 0.0
        }
