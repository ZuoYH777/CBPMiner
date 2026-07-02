# coding=gbk
from collections import Counter
import copy
import time
import net as nt
import comp_utils as cu
from lts import LTS, Tran
import lts_utils as lu
import mining_utils as mu


# 1.发现角色模型----------------------------------------------------------
def CCHP_Discovery(df):
    non_duplicate_df = mu.remove_duplicate_groups(copy.deepcopy(df))
    roles, optional_roles = mu.get_roles(non_duplicate_df)
    print(roles, optional_roles)
    IHPs = []
    for i, dep in enumerate(roles):
        print('dep', dep)
        sub_df = mu.gen_sub_log(df, dep)
        if dep in optional_roles:
            IHP = mu.IHP_Discovery_all(sub_df, non_duplicate_df, i, True)
        else:
            IHP = mu.IHP_Discovery_all(sub_df, non_duplicate_df, i, False)
        IHPs.append(IHP)
    comp_net = cu.get_compose_net_async(IHPs)
    init_res = mu.get_init_res(df, comp_net.res_places)
    comp_net.source = nt.Marking(comp_net.source.get_infor() + init_res)
    return non_duplicate_df, IHPs, comp_net


# 2.根据日志生成可达图(ps:log已经去重)------------------------------------
def gen_kernel(cases, net: nt.OpenNet):
    source, sinks = net.get_start_ends()
    states = [source]; gen_trans = []
    for case in cases:
        marking = source
        for enable_tran in case:
            preset = nt.get_preset(net.get_flows(), enable_tran)
            postset = nt.get_postset(net.get_flows(), enable_tran)
            succ_makring = nt.succ_marking(marking.get_infor(), preset, postset)
            tran = Tran(marking, enable_tran, succ_makring)
            if not nt.marking_is_exist(succ_makring, states): states.append(succ_makring)
            if not tran_is_exist(tran, gen_trans): gen_trans.append(tran)
            marking = succ_makring
    end_markings = []
    msg_places = net.msg_places; res_places = net.res_places
    for marking in states:
        places = marking.get_infor()
        inter_places = [p for p in places if p not in msg_places and p not in res_places]
        new_marking = nt.Marking(inter_places)
        if nt.marking_is_exist(new_marking, sinks): end_markings.append(marking)
    return LTS(source, end_markings, states, gen_trans)


def gen_kernel_adv(cases, net: nt.OpenNet):
    source, sinks = net.get_start_ends()
    flows = net.get_flows()
    preset_of = {}; postset_of = {}
    for flow in flows:
        frm, to = flow.get_infor()
        preset_of.setdefault(to, set()).add(frm)
        postset_of.setdefault(frm, set()).add(to)
    preset_of = {k: list(v) for k, v in preset_of.items()}
    postset_of = {k: list(v) for k, v in postset_of.items()}
    sink_keys = {tuple(sorted(s.get_infor())) for s in sinks}
    states = [source]
    state_keys = {tuple(sorted(source.places))}
    gen_trans = []
    seq_map = {}
    total_cases = len(cases); report_step = max(1, total_cases // 10)
    print('  [gen_kernel_adv] 开始处理 {} 个case (每{}个报告进度)'.format(total_cases, report_step), flush=True)
    for case_idx, case in enumerate(cases):
        if case_idx > 0 and case_idx % report_step == 0:
            print('  [gen_kernel_adv] {}/{} cases ({}%), states={}, trans={}'.format(
                case_idx, total_cases, 100*case_idx//total_cases, len(states), len(gen_trans)), flush=True)
        marking = source
        for enable_tran in case:
            key = tuple(sorted(marking.places))
            if key in seq_map:
                cache = seq_map[key]
                if enable_tran in cache:
                    marking = cache[enable_tran]
                else:
                    preset = preset_of.get(enable_tran, [])
                    postset = postset_of.get(enable_tran, [])
                    succ_marking = nt.succ_marking(marking.get_infor(), preset, postset)
                    tran = Tran(marking, enable_tran, succ_marking)
                    gen_trans.append(tran)
                    succ_key = tuple(sorted(succ_marking.places))
                    if succ_key not in state_keys:
                        state_keys.add(succ_key); states.append(succ_marking)
                    cache[enable_tran] = succ_marking
                    marking = succ_marking
            else:
                preset = preset_of.get(enable_tran, [])
                postset = postset_of.get(enable_tran, [])
                succ_marking = nt.succ_marking(marking.get_infor(), preset, postset)
                tran = Tran(marking, enable_tran, succ_marking)
                gen_trans.append(tran)
                succ_key = tuple(sorted(succ_marking.places))
                if succ_key not in state_keys:
                    state_keys.add(succ_key); states.append(succ_marking)
                seq_map[key] = {enable_tran: succ_marking}
                marking = succ_marking
    end_markings = []
    msg_places = net.msg_places; res_places = net.res_places
    for marking in states:
        places = marking.get_infor()
        inter_places = [p for p in places if p not in msg_places and p not in res_places]
        if tuple(sorted(inter_places)) in sink_keys: end_markings.append(marking)
    return LTS(source, end_markings, states, gen_trans)


def tran_is_exist(tran: Tran, trans):
    for temp_tran in trans:
        if Counter(temp_tran.state_from.get_infor()) == Counter(
                tran.state_from.get_infor(
                )) and temp_tran.label == tran.label and Counter(
                    temp_tran.state_to.get_infor()) == Counter(
                        tran.state_to.get_infor()):
            return True
    return False


def get_unstable_tasks(kernel: LTS, net: nt.OpenNet):
    driver_map = {}
    for tran in kernel.trans:
        key = tuple(sorted(tran.state_from.places))
        if key not in driver_map: driver_map[key] = set()
        driver_map[key].add(tran.label)
    flows = net.get_flows()
    preset_counter_of = {}
    inhibitor_of = {}
    for tran in net.trans:
        preset = nt.get_preset(flows, tran)
        preset_counter_of[tran] = Counter(preset)
        inhib = [pl for [pl, tr] in net.inhibitor_arcs if tr == tran]
        inhibitor_of[tran] = set(inhib)
    def is_enabled(tran, marking):
        if inhibitor_of[tran] & set(marking.places): return False
        cou = Counter(marking.places)
        cou.subtract(preset_counter_of[tran])
        return all(v >= 0 for v in cou.values())
    total_states = len(kernel.states); report_step = max(1, total_states // 5)
    print('  [get_unstable_tasks] 开始处理 {} 个states'.format(total_states), flush=True)
    unstable_tasks = set()
    for state_idx, marking in enumerate(kernel.states):
        if state_idx > 0 and state_idx % report_step == 0:
            print('  [get_unstable_tasks] {}/{} states ({}%)'.format(
                state_idx, total_states, 100*state_idx//total_states), flush=True)
        enable_trans = [t for t in net.trans if is_enabled(t, marking)]
        driver_trans = driver_map.get(tuple(sorted(marking.places)), set())
        unstable_tasks.update(set(enable_trans) - driver_trans)
    return list(unstable_tasks)


def get_driver_trans(marking, kernel: LTS):
    driver_trans = set()
    for tran in kernel.trans:
        if nt.equal_markings(tran.state_from, marking):
            driver_trans.add(tran.label)
    return driver_trans


def gen_CDs(nets, kernel: LTS, unstable_tasks):
    label_index = {}
    for tran in kernel.trans:
        sf, label, st = tran.get_infor()
        if label not in label_index: label_index[label] = []
        label_index[label].append((sf, st))
    label_keys = set(label_index.keys())
    always_visual = set(unstable_tasks) & label_keys
    always_tau = set()
    net_dependent = set()
    for label in label_index:
        if label in always_visual: continue
        ls = label.split('_')
        if len(ls) <= 1: always_tau.add(label)
        else: net_dependent.add(label)
    hide_kernels = get_hide_kernels(nets, kernel, label_index, always_visual, always_tau, net_dependent)
    unstable_set = set(unstable_tasks)
    CDs = []
    for i, net in enumerate(nets):
        print('  [gen_CDs] net {}/{} ...'.format(i+1, len(nets)), flush=True)
        CD_trans = []
        hide_kernel = hide_kernels[i]
        min_hide_kernel = lu.min_lts(hide_kernel, i)
        net_trans_set = set(net.trans)
        index = 0
        for tran in min_hide_kernel.trans:
            state_from, label, state_to = tran.get_infor()
            if label not in net_trans_set and label in unstable_set:
                cood_state = 'CS{}{}'.format(i, index); index += 1
                temp_tran1 = Tran(state_from, 'sync_1_{}'.format(label), cood_state)
                temp_tran2 = Tran(cood_state, 'sync_2_{}'.format(label), state_to)
                CD_trans.append(temp_tran1); CD_trans.append(temp_tran2)
            elif label in net_trans_set and label in unstable_set:
                cood_state1 = 'CS{}{}'.format(i, index); index += 1
                temp_tran1 = Tran(state_from, 'sync_1_{}'.format(label), cood_state1)
                cood_state2 = 'CS{}{}'.format(i, index); index += 1
                temp_tran2 = Tran(cood_state1, label, cood_state2)
                temp_tran3 = Tran(cood_state2, 'sync_2_{}'.format(label), state_to)
                CD_trans.append(temp_tran1); CD_trans.append(temp_tran2); CD_trans.append(temp_tran3)
            else:
                CD_trans.append(tran)
        CD_states = []; seen_states = set()
        for CD_tran in CD_trans:
            state_from, label, state_to = CD_tran.get_infor()
            if state_from not in seen_states: seen_states.add(state_from); CD_states.append(state_from)
            if state_to not in seen_states: seen_states.add(state_to); CD_states.append(state_to)
        CD = LTS(min_hide_kernel.start, min_hide_kernel.ends, CD_states, CD_trans)
        CD.start = CD.start.id
        CD.ends = [t.get_infor()[0] for t in CD.ends]
        CDs.append(CD)
    return CDs


# 获取隐藏核（FIX: net.trans 中的稳定变迁也要保留）
def get_hide_kernels(nets, kernel: LTS, label_index, always_visual, always_tau, net_dependent):
    hide_kernels = []
    start = kernel.start; ends = kernel.ends; states = kernel.states
    for net in nets:
        net_trans_set = set(net.trans)
        hide_core_trans = []
        # always_visual: 不稳定任务 → 保留
        for label in always_visual:
            for (sf, st) in label_index[label]:
                hide_core_trans.append(Tran(sf, label, st))
        # always_tau: 无_分隔符的标签 → 默认隐藏
        # FIX: 但如果在 net.trans 中（net自己的稳定变迁），要保留
        for label in always_tau:
            for (sf, st) in label_index[label]:
                if label in net_trans_set:
                    hide_core_trans.append(Tran(sf, label, st))
                else:
                    hide_core_trans.append(Tran(sf, 'tau', st))
        # net_dependent: 有_分隔符的标签 → per-net判断
        for label in net_dependent:
            visible = bool(set(label.split('_')) & net_trans_set)
            for (sf, st) in label_index[label]:
                if visible:
                    hide_core_trans.append(Tran(sf, label, st))
                elif label in net_trans_set:
                    # FIX: net自己的变迁（即使分解后不匹配）也要保留
                    hide_core_trans.append(Tran(sf, label, st))
                else:
                    hide_core_trans.append(Tran(sf, 'tau', st))
        hide_kernel = LTS(start, ends, states, hide_core_trans)
        hide_kernels.append(hide_kernel)
    return hide_kernels


# 5.生成组合行为---------------------------------------------
def gen_compose_behavior(comp_net, CDs):
    gen_markings = []; gen_trans = []; comp_trans = []
    init_marking = comp_net.source; gen_markings.append(init_marking)
    init_CD_state = []
    for lts in CDs:
        start, ends, states, trans = lts.get_infor()
        init_CD_state.append(start)
    init_comp_state = [init_marking, init_CD_state]
    visiting_queue = [init_comp_state]; visited_queue = [init_comp_state]
    while visiting_queue:
        [marking, CD_state] = visiting_queue.pop(0)
        enable_trans = nt.get_enable_trans(comp_net, marking)
        succ_trans = lu.succ_trans(CD_state, CDs)
        for succ_tran in succ_trans:
            state_from, label, state_to = succ_tran.get_infor()
            if label.startswith('sync_'):
                to_comp_state = [marking, state_to]
                comp_trans.append(Tran([marking, CD_state], label, to_comp_state))
                if not is_visited_comp_state(to_comp_state, visited_queue):
                    visiting_queue.append(to_comp_state); visited_queue.append(to_comp_state)
            else:
                sync_trans = [tran for tran in enable_trans if tran == label]
                for sync_tran in sync_trans:
                    preset = nt.get_preset(comp_net.get_flows(), sync_tran)
                    postset = nt.get_postset(comp_net.get_flows(), sync_tran)
                    to_marking = nt.succ_marking(marking.get_infor(), preset, postset)
                    to_comp_state = [to_marking, state_to]
                    if not nt.marking_is_exist(to_marking, gen_markings): gen_markings.append(to_marking)
                    if not is_exist(marking, label, to_marking, gen_trans): gen_trans.append(Tran(marking, label, to_marking))
                    comp_trans.append(Tran([marking, CD_state], label, to_comp_state))
                    if not is_visited_comp_state(to_comp_state, visited_queue):
                        visiting_queue.append(to_comp_state); visited_queue.append(to_comp_state)
    end_markings = []
    for marking in gen_markings:
        if is_end_marking(marking, comp_net): end_markings.append(marking)
    gen_behavior = LTS(init_marking, end_markings, gen_markings, gen_trans)
    comp_ends = []
    for comp_state in visited_queue:
        if is_end_marking(comp_state[0], comp_net) and lu.is_comp_ends(comp_state[1], CDs):
            comp_ends.append(comp_state)
    comp_behavior = LTS(init_comp_state, comp_ends, visited_queue, comp_trans)
    return gen_behavior, comp_behavior


def is_visited_comp_state(comp_state, visited_queue):
    for temp_comp_state in visited_queue:
        if nt.equal_markings(temp_comp_state[0], comp_state[0]) and temp_comp_state[1] == comp_state[1]:
            return True
    return False


def is_end_marking(marking, comp_net):
    msg_places = comp_net.msg_places; res_places = comp_net.res_places
    places = marking.get_infor()
    inter_places = [p for p in places if p not in msg_places and p not in res_places]
    new_marking = nt.Marking(inter_places)
    if nt.marking_is_exist(new_marking, comp_net.sinks): return True
    return False


def is_exist(marking, label, to_marking, gen_trans):
    for tran in gen_trans:
        if nt.equal_markings(tran.state_from, marking) and tran.label == label and nt.equal_markings(tran.state_to, to_marking):
            return True
    return False


