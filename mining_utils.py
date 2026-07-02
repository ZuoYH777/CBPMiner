# coding=gbk
from ast import literal_eval
import pandas as pd
import pm4py
import net as nt
import copy
from lts import LTS


# 1.先按case_id分组,再对每个分组内的tran列应用list函数------------------------------
# 本质上是获得所有只由变迁组成的不重复的cases
def gen_cases(df):
    grouped = df.groupby('case_id')['tran'].apply(list).reset_index()
    # 获取grouped的所有tran列,并将其添加到列表cases中
    cases = grouped['tran'].tolist()
    return cases


# 2.csv日志转为df进行处理--------------------------------------------------
def csv_to_df(csv_file):
    df = pd.read_csv(csv_file)
    # ps:case_id是字符串类型
    df['case_id'] = df['case_id'].astype(str)
    # 消息,资源和角色是list类型
    df['rec_msg'] = df['rec_msg'].apply(literal_eval)
    df['send_msg'] = df['send_msg'].apply(literal_eval)
    df['req_res'] = df['req_res'].apply(literal_eval)
    df['rel_res'] = df['rel_res'].apply(literal_eval)
    df['roles'] = df['roles'].apply(literal_eval)
    # timestamp是datetime类型
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    print(df)
    return df


# 3.根据角色将日志切分为子日志-----------------------------------------------
def gen_sub_log(df, role):
    filtered_df = df[df['roles'].apply(lambda x: role in x)]
    return filtered_df


# 4.获得所有角色及可选角色---------------------------------------------------
def get_roles(df):
    # df = remove_duplicate_groups(df)
    roles = df['roles'].explode().unique().tolist()
    optional_roles = set()
    for case_id, group in df.groupby('case_id'):
        case_roles = group['roles'].explode().unique().tolist()
        optional_roles = optional_roles.union(set(roles) - set(case_roles))
    return roles, list(optional_roles)


# 5.过滤掉具有相同变迁列表的分组,保留整组原始行--------------------------------
def remove_duplicate_groups(df,
                            group_col='case_id',
                            value_col='tran',
                            ignore_order=False):
    '''
    参数:
    df:原始DataFrame
    group_col:分组列名
    value_col:用于比较的值列名
    ignore_order:是否忽略值的顺序(默认False,考虑顺序)
    返回:过滤后的DataFrame
    '''
    seen = {}
    groups = df.groupby(group_col)
    unique_ids = []

    for name, group in groups:
        values = group[value_col].values

        # 根据ignore_order参数决定是否排序值
        if ignore_order:
            values_sorted = sorted(values)
            key = tuple(values_sorted)
        else:
            key = tuple(values)

        # 如果是新出现的值组合，保留整组
        if key not in seen:
            seen[key] = True
            unique_ids.append(name)

    # 返回过滤后的DataFrame（保留原始列）
    return df[df[group_col].isin(unique_ids)].reset_index(drop=True)


# 6.调用IM算法挖掘BP----------------------------------------------------
'''
三种挖掘方式:
1)考虑消息,资源,可选BP的发现
2)考虑消息和资源,不考虑可选BP的发现
3)考虑消息,不考虑资源和可选BP的发现
'''


def IHP_Discovery_all(sub_df, non_duplicate_df, marker, is_optional):
    net, im, fm = pm4py.discover_petri_net_inductive(sub_df,
                                                     activity_key='tran',
                                                     case_id_key='case_id',
                                                     timestamp_key='timestamp')
    # print(net, im, fm)
    # pm4py.view_petri_net(net, im, fm)

    places = []
    inner_places = []
    for temp_place in net.places:
        place = transform_name(temp_place.name, marker)
        places.append(place)
        inner_places.append(place)
    print('places', places, inner_places)

    trans = []
    label_map = {}
    for t in net.transitions:
        # t.name为挖掘算法起的名称是一堆字符串,t.label例如't1','t2'
        tran = t.label
        # ps:要注意变迁是引入的路由变迁
        if tran is None:
            tran = transform_name(t.name, marker)
        trans.append(tran)
        label_map[tran] = tran
    print('trans', trans, label_map)

    flows = []
    for arc in net.arcs:
        if isinstance(arc.source, pm4py.objects.petri_net.obj.PetriNet.Place):
            flow_from = transform_name(arc.source.name, marker)
            flow_to = arc.target.label
            # ps:要注意变迁是引入的路由变迁
            if flow_to is None:
                flow_to = transform_name(arc.target.name, marker)
            # print(flow_from, flow_to)
            flows.append(nt.Flow(flow_from, flow_to))
        else:
            flow_from = arc.source.label
            # ps:要注意变迁是引入的路由变迁
            if flow_from is None:
                flow_from = transform_name(arc.source.name, marker)
            flow_to = transform_name(arc.target.name, marker)
            # print(flow_from, flow_to)
            flows.append(nt.Flow(flow_from, flow_to))

    msg_places = set()
    res_places = set()
    for tran in trans:
        # tran是挖掘中引入的路由变迁没有对应的行
        all_rows = non_duplicate_df[non_duplicate_df['tran'] == tran]
        if all_rows.empty:
            continue
        # 第一个迁移为tran的行
        row = all_rows.iloc[0]
        # 提取rec_msg列（list类型）
        rec_msg = row['rec_msg']
        msg_places = msg_places.union(set(rec_msg))
        for rec_msg_i in rec_msg:
            flows.append(nt.Flow(rec_msg_i, tran))
        # 提取send_msg列（list类型）
        send_msg = row['send_msg']
        msg_places = msg_places.union(set(send_msg))
        for send_msg_i in send_msg:
            flows.append(nt.Flow(tran, send_msg_i))
        # 提取req_res列（list类型）
        req_res = row['req_res']
        res_places = res_places.union(set(req_res))
        for req_res_i in req_res:
            flows.append(nt.Flow(req_res_i, tran))
        # 提取rel_res列（list类型）
        rel_res = row['rel_res']
        res_places = res_places.union(set(rel_res))
        for rel_res_i in rel_res:
            flows.append(nt.Flow(tran, rel_res_i))

    msg_places = list(msg_places)
    res_places = list(res_places)
    places = places + msg_places + res_places

    source = nt.Marking([transform_name('source', marker)])
    print(source)
    # 考虑可选BP,则source和sink都要考虑
    sinks = []
    if is_optional:
        sinks.append(nt.Marking([transform_name('source', marker)]))
        sinks.append(nt.Marking([transform_name('sink', marker)]))
    else:
        sinks.append(nt.Marking([transform_name('sink', marker)]))

    open_net = nt.OpenNet(source, sinks, places, trans, label_map, flows)
    open_net.inner_places = inner_places
    open_net.msg_places = msg_places
    open_net.res_places = res_places
    # open_net.net_to_dot('open_net{}'.format(marker), False)
    return open_net


# 重命名字符串
def transform_name(name, marker):
    if '_' in name:
        # 找到第一个下划线的位置
        idx = name.find('_')
        # 分割字符串并在中间插入标记
        return name[:idx] + f'_{marker}_' + name[idx + 1:]
    else:
        # 直接添加标记
        return f'{name}_{marker}'


# 7.由日志获取初始资源---------------------------------------------------
def get_init_res(df, res_places):
    init_res = []
    # 去重
    non_duplicate_df = remove_duplicate_groups(copy.deepcopy(df))
    for res in res_places:
        skip_outer = False
        for case_id, group in non_duplicate_df.groupby('case_id'):
            # 按时间戳排序(确保顺序遍历)
            sorted_group = group.sort_values('timestamp')
            for index, row in sorted_group.iterrows():
                req_res = row['req_res']
                rel_res = row['rel_res']
                # 先计算请求是因为存在{(res,t),(t,res)}
                if res in req_res:
                    # 则加入初始资源
                    init_res.append(res)
                    skip_outer = True
                    break  # 跳出第三层循环
                elif res in rel_res:
                    # 则不是初始资源
                    skip_outer = True
                    break  # 跳出第三层循环
            if skip_outer:
                break  # 跳出第二层循环

    return init_res


# 将一个lts转换为邻接表
def lts_to_adjacency_list(lts: LTS):
    adjacency_list = {}
    # ps:先初始化每个节点
    for state in lts.states:
        adjacency_list[state] = []
    for tran in lts.trans:
        state_from, label, state_to = tran.get_infor()
        adjacency_list[state_from].append((state_to, label))
    return adjacency_list
