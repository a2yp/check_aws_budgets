#!/usr/bin/env python3
"""
check_aws_budgets.py

An Icinga/Nagios plug-in to check budgets in an account

Author: Frank Wittig <frank@e5k.de>
Source: https://github.com/elias5000/check_aws_budgets
"""

import sys
from argparse import ArgumentParser

import boto3
from botocore.exceptions import BotoCoreError, ClientError

STATE_OK = 0
STATE_WARN = 1
STATE_CRIT = 2
STATE_UNKNOWN = 3


def fetch_budget(name):
    """
    Fetch single budget from account
    :param name: budget name
    :return:
    """
    try:
        caller = boto3.client('sts').get_caller_identity()
        client = boto3.client('budgets')
        return client.describe_budget(AccountId=caller['Account'], BudgetName=name)['Budget']
    except (BotoCoreError, ClientError) as err:
        print(f"UNKNOWN - {err}")
        sys.exit(STATE_UNKNOWN)


def fetch_budgets():
    """
    Fetch all budgets from account
    :return:
    """
    try:
        caller = boto3.client('sts').get_caller_identity()
        client = boto3.client('budgets')
        paginator = client.get_paginator('describe_budgets')
        budgets = []
        for page in paginator.paginate(AccountId=caller['Account']):
            for budget in page['Budgets']:
                budgets.append(budget)
        return budgets

    except BotoCoreError as err:
        print(f"UNKNOWN - {err}")
        sys.exit(STATE_UNKNOWN)


def get_overspend(budgets):
    """
    Return budgets with overspend flag as dict
    :param budgets: list of budgets
    :return:
    """
    res = {
        True: [],
        False: []
    }
    for budget in budgets:
        name = budget['BudgetName']
        limit = float(budget['BudgetLimit']['Amount'])
        try:
            forecast = float(budget['CalculatedSpend']['ForecastedSpend']['Amount'])
            res[forecast > limit].append(f"{name}(fcst:{forecast:.2f};limit:{limit:.2f})")
        except KeyError:
            actual = float(budget['CalculatedSpend']['ActualSpend']['Amount'])
            res[actual > limit].append("{name}(act:{actual:.2f};limit:{limit:.2f})")
    return res


def get_perfdata(budgets: list) -> str:
    """Return performance data string
    :param budgets: list of budgets
    :return: performance data
    """
    perfdata = []
    for budget in budgets:
        label = budget["BudgetName"]
        value = budget["CalculatedSpend"]["ActualSpend"]["Amount"]
        uom = budget["CalculatedSpend"]["ActualSpend"]["Unit"]
        limit = budget["BudgetLimit"]["Amount"]

        perfdata.append(f"'{label}'={value}{uom};{limit};{limit}")
    return f"| {' '.join(perfdata)}"


def main():
    """ CLI user interface """
    parser = ArgumentParser()
    parser.add_argument('--budget', help='budget name')

    args = parser.parse_args()

    if args.budget:
        budgets = [fetch_budget(args.budget)]
    else:
        budgets = fetch_budgets()

    overspend = get_overspend(budgets)
    perfadata = get_perfdata(budgets)

    if overspend[True]:
        print(f"Budget forecast exceeds limit: {', '.join(overspend[True])}{perfadata}")
        sys.exit(STATE_CRIT)

    print(f"Budgets forecast within limit: {', '.join(overspend[False])}{perfadata}")
    sys.exit(STATE_OK)


if __name__ == '__main__':
    main()
