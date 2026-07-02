# coding=gbk
from collections import Counter
import copy
import itertools
from lts import LTS, Tran
import mining_utils as mu


# 1.定义最小化过程中合并状态------------------------------------------
class MinState(object):

    def __init__(self, id, states):
        self.id = id
        self.states = states

    def get_infor(self):
        return self.id, self.states


# 2.1获得state的tau闭包---------------------------------------------
def gen_tau_closure(state, lts):
    ing_queue = [state]
    ed_queue = [state]
    while ing_queue:
        from_state = ing_queue.pop(0)
        tau_states = gen_tau_states(from_state, lts)
        for tau_state in tau_states:
            if tau_state not in ed_queue:
                ing_queue.append(tau_state)
                ed_queue.append(tau_state)
    return ed_queue


# 获得state的tau迁移状态
def gen_tau_states(state, lts):
    tau_states = set()
    start, ends, states, trans = lts.get_infor()
    for tran in trans:
        state_from, label, state_to = tran.get_infor()
        if state_from == state and label == 'tau':
            tau_states.add(state_to)
    return list(tau_states)


def gen_tau_closure_adv(state, adj_list):
    ing_queue = [state]
    ed_queue = [state]
    ed_set = {state}
    while ing_queue:
        from_state = ing_queue.pop(0)
        tau_states = gen_tau_states_adv(from_state, adj_list)
        for tau_state in tau_states:
            if tau_state not in ed_set:
                ed_set.add(tau_state)
                ing_queue.append(tau_state)
                ed_queue.append(tau_state)
    return ed_queue


# 获得state的tau迁移状态
def gen_tau_states_adv(state, adj_list):
    tau_states = set()
    for val in adj_list[state]:
        (state_to, label) = val
        if label == 'tau':
            tau_states.add(state_to)
    return list(tau_states)


# 2.2获得state的传递闭包---------------------------------------------
def gen_tran_closure(state, adj_list):
    ing_queue = [state]
    ed_queue = [state]
    while ing_queue:
        from_state = ing_queue.pop(0)
        tran_states = gen_tran_states(from_state, adj_list)
        for tran_state in tran_states:
            if tran_state not in ed_queue:
                ing_queue.append(tran_state)
                ed_queue.append(tran_state)
    return ed_queue


def gen_tran_states(state, adj_list):
    tran_states = set()
    for val in adj_list[state]:
        (state_to, label) = val
        tran_states.add(state_to)
    return list(tran_states)


def one_tran_labels(state, adj_list):
    one_trans = set()
    for val in adj_list[state]:
        (state_to, label) = val
        one_trans.add(label)
    return list(one_trans)


def gen_tran_closure_no_back(state, back_trans, lts):
    ing_queue = [state]
    ed_queue = [state]
    while ing_queue:
        from_state = ing_queue.pop(0)
        tran_states = gen_tran_states_no_back(from_state, back_trans, lts)
        for tran_state in tran_states:
            if tran_state not in ed_queue:
                ing_queue.append(tran_state)
                ed_queue.append(tran_state)
    return ed_queue


def gen_tran_states_no_back(state, back_trans, lts):
    tran_states = set()
    start, ends, states, trans = lts.get_infor()
    for tran in trans:
        state_from, label, state_to = tran.get_infor()
        if label in back_trans:
            continue
        if state_from == state:
            tran_states.add(state_to)
    return list(tran_states)


def min_lts(lts, flag):

    adj_list = mu.lts_to_adjacency_list(lts)

    min_states = []
    min_trans = []

    start, ends, states, trans = lts.get_infor()

    # 主循环内不再重复BFS，直接查缓存
    tau_cache = {}
    for s in states:
        tau_cache[s] = set(gen_tau_closure_adv(s, adj_list))

    name_succ = {}
    for s in states:
        for (to, lbl) in adj_list[s]:
            if lbl != 'tau':
                if lbl not in name_succ:
                    name_succ[lbl] = {}
                if s not in name_succ[lbl]:
                    name_succ[lbl][s] = set()
                name_succ[lbl][s].add(to)

    def move_fast(from_closure, name):
        reach = set()
        nmap = name_succ.get(name, {})
        for s in from_closure:
            if s in nmap:
                reach.update(nmap[s])
        return reach

    def get_tau(s):
        if s in tau_cache:
            return tau_cache[s]
        return set(gen_tau_closure_adv(s, adj_list))

    index = 0
    init_min_state_id = '{}{}'.format(flag, index)
    init_closure = get_tau(start)
    init_min_state = MinState(init_min_state_id, list(init_closure))
    min_states.append(init_min_state)

    names = get_lts_names(lts)

    visiting_queue = [init_min_state]
    visited_queue = [init_min_state]
    closure_map = {frozenset(init_closure): init_min_state_id}

    while visiting_queue:

        from_min_state = visiting_queue.pop(0)
        from_id, from_closure = from_min_state.get_infor()

        for name in names:

            reach_states = move_fast(from_closure, name)
            if not reach_states:
                continue
            to_closure = set()
            for reach_state in reach_states:
                to_closure.update(get_tau(reach_state))

            idf = is_gen_closure(to_closure, visited_queue, closure_map)
            if idf is None:
                index += 1
                to_id = '{}{}'.format(flag, index)
                to_min_state = MinState(to_id, list(to_closure))
                min_states.append(to_min_state)
                min_tran = Tran(from_id, name, to_id)
                min_trans.append(min_tran)
                visiting_queue.append(to_min_state)
                visited_queue.append(to_min_state)
                closure_map[frozenset(to_closure)] = to_id
            else:
                min_tran = Tran(from_id, name, idf)
                min_trans.append(min_tran)

    return LTS(init_min_state, get_min_ends(ends, visited_queue), min_states, min_trans)


# 获得最小化后的终止标识
def get_min_ends(ends, ed_queue):
    min_ends = []
    for min_state in ed_queue:
        id, states = min_state.get_infor()
        if set(states).intersection(set(ends)):
            min_ends.append(min_state)
    return min_ends


# 判断新状态是否生产过
def is_gen_closure(to_closure, ed_queue, closure_map=None):
    if closure_map is not None:
        key = frozenset(to_closure)
        return closure_map.get(key, None)
    for min_state in ed_queue:
        id, states = min_state.get_infor()
        if Counter(states) == Counter(list(to_closure)):
            return id
    return None


# 获得得states中每个状态迁移name后的状态集
def move(states, name, adj_list):
    reach_states = set()
    for state in states:
        tran_states = get_tran_states(state, name, adj_list)
        reach_states = reach_states.union(tran_states)
    return list(reach_states)


def get_tran_states(state, name, adj_list):
    tran_states = set()
    for val in adj_list[state]:
        (state_to, label) = val
        if label == name:
            tran_states.add(state_to)
    return tran_states


def get_lts_names(lts):
    names = set()
    start, ends, states, trans = lts.get_infor()
    for tran in trans:
        state_from, label, state_to = tran.get_infor()
        if label != 'tau':
            names.add(label)
    return list(names)


# 4.同步组合lts----------------------------------------------------
def lts_compose(lts_list):

    comp_start = []
    for lts in lts_list:
        start, ends, states, trans = lts.get_infor()
        comp_start.append(start)

    comp_trans = []
    inner_name_map, inter_name_map = divide_names(lts_list)

    visiting_queue = [comp_start]
    visited_queue = [comp_start]

    while visiting_queue:

        comp_state = visiting_queue.pop(0)
        sync_tran_set = []
        for i, state in enumerate(comp_state):
            succ_trans = get_succ_trans(state, lts_list[i])
            sync_trans_list = []
            for succ_tran in succ_trans:
                state_from, label, state_to = succ_tran.get_infor()
                if label in inner_name_map.keys():
                    succ_comp_state = copy.deepcopy(comp_state)
                    succ_comp_state[i] = state_to
                    comp_trans.append(Tran(str(comp_state), label, str(succ_comp_state)))
                    if succ_comp_state not in visited_queue:
                        visiting_queue.append(succ_comp_state)
                        visited_queue.append(succ_comp_state)
                else:
                    sync_trans_list.append(succ_tran)
            sync_tran_set.append(sync_trans_list)

        null_size = 0
        for i, succ_tran in enumerate(sync_tran_set):
            if not succ_tran:
                sync_tran_set[i].append(-1)
                null_size += 1

        if null_size == len(sync_tran_set):
            continue

        for tran_list in itertools.product(*sync_tran_set):
            if is_sync_trans(tran_list, inter_name_map):
                succ_comp_state = copy.deepcopy(comp_state)
                for i, tran in enumerate(tran_list):
                    if tran == -1:
                        continue
                    state_from, label, state_to = tran.get_infor()
                    succ_comp_state[i] = state_to
                if succ_comp_state not in visited_queue:
                    visiting_queue.append(succ_comp_state)
                    visited_queue.append(succ_comp_state)
                comp_trans.append(Tran(str(comp_state), label, str(succ_comp_state)))

    comp_ends = []
    for comp_state in visited_queue:
        if is_comp_ends(comp_state, lts_list):
            comp_ends.append(comp_state)

    return LTS(str(comp_start), [str(comp_end) for comp_end in comp_ends],
               [str(state) for state in visited_queue], comp_trans)


def is_comp_ends(comp_state, lts_list):
    for i, state in enumerate(comp_state):
        start, ends, states, trans = lts_list[i].get_infor()
        if state not in ends:
            return False
    return True


def is_sync_trans(tran_list, inter_name_map):
    names = set()
    index_list = []
    for i, tran in enumerate(tran_list):
        if tran == -1:
            continue
        state_from, label, state_to = tran.get_infor()
        names.add(label)
        index_list.append(i)
    if len(names) == 1:
        name = list(names)[0]
        if inter_name_map[name] == index_list:
            return True
    return False


def divide_names(lts_list):
    names = get_all_names(lts_list)
    inner_name_map = {}
    inter_name_map = {}
    for name in names:
        name_index = get_name_index(name, lts_list)
        if len(name_index) < 2:
            inner_name_map[name] = name_index
        else:
            inter_name_map[name] = name_index
    return inner_name_map, inter_name_map


def get_name_index(name, lts_list):
    name_index = []
    for i, lts in enumerate(lts_list):
        labels = lts.get_labels()
        if name in labels:
            name_index.append(i)
    return name_index


def get_all_names(lts_list):
    names = set()
    for lts in lts_list:
        labels = lts.get_labels()
        names = names.union(set(labels))
    return list(names)


def get_succ_trans(state, lts):
    succ_trans = []
    start, ends, states, trans = lts.get_infor()
    for tran in trans:
        state_from, label, state_to = tran.get_infor()
        if state_from == state:
            succ_trans.append(tran)
    return succ_trans


# 5.获取同步组合lts的一次迁移集-----------------------------------------------
def succ_trans(comp_state, lts_list):

    comp_trans = []
    inner_name_map, inter_name_map = divide_names(lts_list)

    sync_tran_set = []
    for i, state in enumerate(comp_state):
        succ_trans = get_succ_trans(state, lts_list[i])
        sync_tran_list = []
        for succ_tran in succ_trans:
            state_from, label, state_to = succ_tran.get_infor()
            if label in inner_name_map.keys():
                succ_comp_state = copy.deepcopy(comp_state)
                succ_comp_state[i] = state_to
                comp_trans.append(Tran(comp_state, label, succ_comp_state))
            else:
                sync_tran_list.append(succ_tran)
        sync_tran_set.append(sync_tran_list)

    null_size = 0
    for i, succ_tran in enumerate(sync_tran_set):
        if not succ_tran:
            sync_tran_set[i].append(-1)
            null_size += 1

    if null_size != len(sync_tran_set):
        for tran_list in itertools.product(*sync_tran_set):
            if is_sync_trans(tran_list, inter_name_map):
                succ_comp_state = copy.deepcopy(comp_state)
                for i, tran in enumerate(tran_list):
                    if tran == -1:
                        continue
                    state_from, label, state_to = tran.get_infor()
                    succ_comp_state[i] = state_to
                comp_trans.append(Tran(comp_state, label, succ_comp_state))

    return comp_trans


