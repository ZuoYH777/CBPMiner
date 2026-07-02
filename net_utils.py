# coding=gbk

from collections import Counter
import copy
from lts import LTS, Tran
import net as nt
import net_gen as ng
import comp_utils as cu
# import stub_utils as su
import lts_utils as lu
import mining_utils as mu


# 1.1产生可达图(资源用资源库所标识,每个资源对应一个资源库所)------------------------------
def gen_rg(net: nt.OpenNet):

    source, sinks = net.get_start_ends()
    flows = net.get_flows()

    # 预计算preset/postset/inhibit字典，避免每次扫描所有流
    preset_of = {}
    postset_of = {}
    for f in flows:
        frm, to = f.get_infor()
        preset_of.setdefault(to, []).append(frm)
        postset_of.setdefault(frm, []).append(to)

    inhib_of = {}
    for pl, tr in net.inhibitor_arcs:
        inhib_of.setdefault(tr, set()).add(pl)

    sink_keys = {frozenset(s.get_infor()) for s in sinks}
    msg_set = set(net.msg_places)
    res_set = set(net.res_places)

    gen_trans = []
    visiting_queue = [source]
    visited_set = {frozenset(source.get_infor())}

    def is_enabled(tran, marking_places):

        if tran in inhib_of and inhib_of[tran] & set(marking_places):
            return False
        pre = preset_of.get(tran, [])
        cou = Counter(marking_places)
        cou.subtract(pre)
        return all(v >= 0 for v in cou.values())

    while visiting_queue:
        marking = visiting_queue.pop()
        marking_places = marking.get_infor()

        for tran in net.trans:
            if is_enabled(tran, marking_places):
                pre = preset_of.get(tran, [])
                post = postset_of.get(tran, [])
                succ_marking = nt.succ_marking(marking_places, pre, post)
                sk = frozenset(succ_marking.get_infor())
                tran_obj = Tran(marking, tran, succ_marking)
                gen_trans.append(tran_obj)
                if sk not in visited_set:
                    visited_set.add(sk)
                    visiting_queue.append(succ_marking)


    visited_list = [source]
    seen = {frozenset(source.get_infor())}
    vq = [source]
    while vq:
        m = vq.pop(0)
        mp = m.get_infor()
        for tran in net.trans:
            if is_enabled(tran, mp):
                pre = preset_of.get(tran, [])
                post = postset_of.get(tran, [])
                sm = nt.succ_marking(mp, pre, post)
                sk = frozenset(sm.get_infor())
                if sk not in seen:
                    seen.add(sk)
                    visited_list.append(sm)
                    vq.append(sm)


    end_markings = []
    for marking in visited_list:
        places = marking.get_infor()
        inter_places = [p for p in places if p not in msg_set and p not in res_set]
        if frozenset(inter_places) in sink_keys:
            end_markings.append(marking)

    return LTS(source, end_markings, visited_list, gen_trans)


def check_net_correctness(net: nt.OpenNet):
    rg = gen_rg(net)
    print('rg size:', len(rg.states))
    lts = rg.rg_to_lts()[0]
    ends = lts.ends

    adj_list = mu.lts_to_adjacency_list(lts)
    # 构建反向邻接表
    reverse_adj = {}
    for state in adj_list:
        if state not in reverse_adj:
            reverse_adj[state] = []
        for (to_state, label) in adj_list[state]:
            reverse_adj.setdefault(to_state, []).append(state)

    # 从所有终态反向BFS一次
    valid_set = set(ends)
    queue = list(ends)
    while queue:
        s = queue.pop(0)
        for pred in reverse_adj.get(s, []):
            if pred not in valid_set:
                valid_set.add(pred)
                queue.append(pred)

    states = lts.states
    if len(valid_set) == len(states):
        return 'Correct'
    if len(valid_set) == 0:
        return 'Fully Incorrect'
    else:
        return 'Partially Correct'


    rg = gen_rg(net)
    print('rg size:', len(rg.states))
    lts = rg.rg_to_lts()[0]
    ends = lts.ends

    adj_list = mu.lts_to_adjacency_list(lts)
    # Build reverse edges for backward BFS
    reverse_adj = {}
    for state in adj_list:
        if state not in reverse_adj:
            reverse_adj[state] = []
        for (to_state, label) in adj_list[state]:
            reverse_adj.setdefault(to_state, []).append(state)

    # Single backward BFS from all end states
    end_set = set(ends)
    valid_set = set(ends)
    queue = list(ends)
    while queue:
        s = queue.pop(0)
        for pred in reverse_adj.get(s, []):
            if pred not in valid_set:
                valid_set.add(pred)
                queue.append(pred)

    states = lts.states
    if len(valid_set) == len(states):
        return 'Correct'
    if len(valid_set) == 0:
        return 'Fully Incorrect'
    else:
        return 'Partially Correct'

def gen_rg_with_res(net):

    source, sinks = net.get_start_ends()

    gen_trans = []  # 产生的变迁集

    # 运行队列和已访问队列
    print('net.init_res', net.init_res)
    visiting_queue = [[source, net.init_res]]
    visited_queue = [[source, net.init_res]]

    # 迭代计算
    while visiting_queue:
        [marking, res] = visiting_queue.pop(0)
        enable_trans = nt.get_enable_trans(net, marking)
        for enable_tran in enable_trans:
            # Note:避免分支中提前将资源消耗掉(每个分支获得资源相同)~~~~~~~~~~~~~~~~~~
            res_copy = copy.deepcopy(res)
            req_res = net.req_res_map[enable_tran]
            # 若当前资源不充足,则跳过当前使能变迁
            if not res_is_suff(res_copy, req_res):
                continue
            # 1)产生后继状态
            preset = nt.get_preset(net.get_flows(), enable_tran)
            postset = nt.get_postset(net.get_flows(), enable_tran)
            succ_makring = nt.succ_marking(marking.get_infor(), preset,
                                           postset)
            succ_res = get_succ_res(res_copy, net.req_res_map[enable_tran],
                                    net.rel_res_map[enable_tran])
            # 2)产生后继变迁(Note:迁移动作以标号进行标识)
            tran = Tran([marking, res], enable_tran, [succ_makring, succ_res])
            gen_trans.append(tran)
            # 添加未访问的状态
            if not state_is_exist([succ_makring, succ_res], visited_queue):
                visiting_queue.append([succ_makring, succ_res])
                visited_queue.append([succ_makring, succ_res])

    # 添加终止状态集(ps:允许消息库所和资源库所不为空)
    end_states = []
    for state in visited_queue:
        [marking, res] = state
        if nt.marking_is_exist(marking, sinks):
            end_states.append(state)

    return LTS([source, net.init_res], end_states, visited_queue, gen_trans)


# 判断当前资源是否充足
def res_is_suff(res, req_res):
    cou = Counter(res)
    cou.subtract(Counter(req_res))
    vals = cou.values()
    for val in vals:
        if val < 0:
            return False
    return True


# 获取变迁迁移后的资源集合(ps:资源是list类型)
def get_succ_res(res, req_res, rel_res):
    # 移除前集
    for rr in req_res:
        if rr in res:
            res.remove(rr)
    succ_res = res + rel_res
    return succ_res


# 判断后继状态是否已存在
def state_is_exist(succ_state, visited_queue):
    [succ_makring, succ_res] = succ_state
    for temp_state in visited_queue:
        [temp_makring, temp_res] = temp_state
        if nt.equal_markings(
                succ_makring,
                temp_makring) and Counter(succ_res) == Counter(temp_res):
            return True
    return False


# 2.1利用稳固集产生可达图(每个资源对应一个资源库所)-----------------------------------------
def gen_rg_with_subset(net: nt.OpenNet):

    source, sinks = net.get_start_ends()
    gen_trans = []  # 产生的变迁集

    # 运行队列和已访问队列
    visiting_queue = [source]
    visited_queue = [source]

    # 迭代计算
    while visiting_queue:
        marking = visiting_queue.pop(0)
        # print(marking.get_infor())
        # Note:只迁移稳固集中使能活动(未考虑消除忽视问题)
        enable_trans = nt.get_enable_trans(net, marking)
        S = get_stubset(net, marking, enable_trans)
        enable_trans = list(set(enable_trans).intersection(set(S)))
        for enable_tran in enable_trans:
            # 1)产生后继标识
            preset = nt.get_preset(net.get_flows(), enable_tran)
            postset = nt.get_postset(net.get_flows(), enable_tran)
            succ_makring = nt.succ_marking(marking.get_infor(), preset,
                                           postset)
            # 2)产生后继变迁(Note:迁移动作以标号进行标识)
            tran = Tran(marking, enable_tran, succ_makring)
            gen_trans.append(tran)
            # 添加未访问的状态
            if not nt.marking_is_exist(succ_makring, visited_queue):
                visiting_queue.append(succ_makring)
                visited_queue.append(succ_makring)

    # 终止标识(ps:允许消息库所和资源库所不为空)
    end_markings = []
    msg_places = net.msg_places
    res_places = net.res_places
    for marking in visited_queue:
        places = marking.get_infor()
        inter_places = [
            place for place in places
            if place not in msg_places and place not in res_places
        ]
        new_marking = nt.Marking(inter_places)
        if nt.marking_is_exist(new_marking, sinks):
            print('end marking:', places)
            end_markings.append(marking)

    return LTS(source, end_markings, visited_queue, gen_trans)


# 2.2利用稳固集产生中间约简可达图(资源用list表示)--------------------------------------
def gen_rrg(net: nt.OpenNet):
    '''
    Note:由于建模采用工作流网,故不存在忽视问题
    '''
    source, sinks = net.get_start_ends()
    gen_trans = []  # 产生的变迁集

    # 运行队列和已访问队列
    visiting_queue = [[source, net.init_res]]
    visited_queue = [[source, net.init_res]]

    # 迭代计算
    while visiting_queue:
        [marking, res] = visiting_queue.pop(0)
        # Note:只迁移稳固集中使能活动
        enable_trans = []
        # 求受到资源约束的使能迁移集
        for tran in nt.get_enable_trans(net, marking):
            # Note:避免分支中提前将资源消耗掉(每个分支获得资源相同)
            res_copy = copy.deepcopy(res)
            req_res = net.req_res_map[tran]
            # 若当前资源充足,则添加使能变迁
            if res_is_suff(res_copy, req_res):
                enable_trans.append(tran)
        S = get_stubset(net, marking, enable_trans)
        enable_trans = list(set(enable_trans).intersection(set(S)))
        for enable_tran in enable_trans:
            # Note:避免分支中提前将资源消耗掉(每个分支获得资源相同)
            res_copy = copy.deepcopy(res)
            # 1)产生后继状态
            preset = nt.get_preset(net.get_flows(), enable_tran)
            postset = nt.get_postset(net.get_flows(), enable_tran)
            succ_makring = nt.succ_marking(marking.get_infor(), preset,
                                           postset)
            succ_res = get_succ_res(res_copy, net.req_res_map[enable_tran],
                                    net.rel_res_map[enable_tran])
            # 2)产生后继变迁(Note:迁移动作以标号进行标识)
            tran = Tran([marking, res], enable_tran, [succ_makring, succ_res])
            gen_trans.append(tran)
            # 添加未访问的状态
            if not state_is_exist([succ_makring, succ_res], visited_queue):
                visiting_queue.append([succ_makring, succ_res])
                visited_queue.append([succ_makring, succ_res])

    # 添加终止状态集(ps:允许消息库所和资源库所不为空)
    end_states = []
    for state in visited_queue:
        [marking, res] = state
        if nt.marking_is_exist(marking, sinks):
            end_states.append(state)

    return LTS([source, net.init_res], end_states, visited_queue, gen_trans)


# 3.计算特定标识的稳固集----------------------------------------------------
def get_stubset(net, marking, enable_trans):
    S = []  # 返回稳固集
    U = []  # 未处理迁移集
    if not enable_trans:  # 没有使能迁移,直接返回空稳固集S
        return S
    else:  # 有使能迁移,随机选择一个使能迁移
        first_act = enable_trans[0]
        # print('first_act', first_act)
        S.append(first_act)
        U.append(first_act)
        while U:
            act = U.pop(0)
            if act in enable_trans:
                N = get_disenabling_trans(net, act)
            else:
                N = get_enabling_trans(net, act, marking)
            # 避免重复添加
            subset = set(N) - set(S)
            U = list(set(U).union(subset))
            # 添加稳固集到S
            S = list(set(S).union(N))
        return S


# 获取导致变迁使能的变迁集(以Id标识)
def get_enabling_trans(net, tran, marking):
    enabling_trans = set()
    places = marking.get_infor()
    preset = nt.get_preset(net.get_flows(), tran)
    for place in preset:
        # 跳过已经含有托肯的库所
        if place in places:
            continue
        # 不重复
        enabling_trans = enabling_trans.union(
            set(nt.get_preset(net.get_flows(), place)))
    return list(enabling_trans)


# 获取变迁的冲突变迁集(以Id标识)
def get_disenabling_trans(net: nt.OpenNet, tran):
    disenabling_trans = []
    trans = net.trans
    preset = nt.get_preset(net.get_flows(), tran)
    for temp_tran in trans:
        # 不包括自己
        if temp_tran == tran:
            continue
        temp_preset = nt.get_preset(net.get_flows(), temp_tran)
        # 前集相交(冲突)
        if set(preset).intersection(set(temp_preset)):
            disenabling_trans.append(temp_tran)
    return disenabling_trans



