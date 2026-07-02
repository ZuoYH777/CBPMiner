# coding=gbk
from net import Flow, Marking, OpenNet
import net_gen as ng
import net_utils as nu
import net as nt
import comp_utils as cu
'''
  定义网组合的工具类
  1.控制流由顺序,选择,并发和迭代组成(无link结构);
  2.迭代结构只含repeat-until结构;
  3.交互是同步+异步的;
  4.ps:每个资源库所对应一个资源;
  5.涉及时间信息.
'''


# 0.将组合开放网中资源映射为库所--------------------------------------------------
def res_to_places(comp_net: OpenNet):
    '''
    Note:默认每个资源库所对应一个资源
    '''
    init_res = comp_net.init_res
    source = comp_net.source
    new_source = Marking(source.get_infor() + init_res)
    comp_net.source = new_source

    res_places = comp_net.res_places
    comp_net.add_places(res_places)

    req_res_map = comp_net.req_res_map
    for tran, req_res in req_res_map.items():
        for res in req_res:
            comp_net.add_flow(res, tran)
    rel_res_map = comp_net.rel_res_map
    for tran, rel_res in rel_res_map.items():
        for res in rel_res:
            comp_net.add_flow(tran, res)

    return comp_net


# 获取com_net中变迁在案例的信息,其中每个资源转换为一个库所
def get_case_infor(nets, comp_net: OpenNet):
    tran_infor = {}
    trans = comp_net.trans
    for tran in trans:
        tran_infor[tran] = {
            'rec_msg':
            list(
                set(nt.get_preset(comp_net.flows, tran))
                & set(comp_net.msg_places)),
            'send_msg':
            list(
                set(nt.get_postset(comp_net.flows, tran))
                & set(comp_net.msg_places)),
            'req_res':
            list(
                set(nt.get_preset(comp_net.flows, tran))
                & set(comp_net.res_places)),
            'rel_res':
            list(
                set(nt.get_postset(comp_net.flows, tran))
                & set(comp_net.res_places)),
            'roles':
            get_roles(tran, nets),
        }
    return tran_infor


def get_roles(tran, nets):
    roles = []
    trans = tran.split('_')
    for t in trans:
        for net in nets:
            if t in net.trans:
                roles.append(net.role)
                break
    return roles


# 1a.组合开放网(同步+异步)--------------------------------------------
'''
这个方法主要是用于建模,即将PIPE中建模的网进行合并
'''


def get_compose_net(nets):
    # gen_sync_trans为合并过程中的中间同步变迁集
    gen_sync_trans = []
    net = compose_nets(nets, gen_sync_trans)
    print('gen_sync_trans: ', gen_sync_trans)
    net.print_infor()
    return net


# 1.1a.组合bag构建组合网---------------------------------------------
def compose_nets(nets, gen_sync_trans):
    if len(nets) == 0:
        print('no bag_nets exist, exit...')
        return
    if len(nets) == 1:
        return nets[0]
    else:
        net = compose_two_nets(nets[0], nets[1], gen_sync_trans)
        for i in range(2, len(nets)):
            net = compose_two_nets(net, nets[i], gen_sync_trans)
        return net


# 组合两个开放网
def compose_two_nets(net1: OpenNet, net2: OpenNet, gen_sync_trans):

    # 1)产生源和终止标识~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    source1, sinks1 = net1.get_start_ends()
    source2, sinks2 = net2.get_start_ends()
    source = Marking(source1.get_infor() + source2.get_infor())
    sinks = []
    for sink1 in sinks1:
        for sink2 in sinks2:
            sink = Marking(sink1.get_infor() + sink2.get_infor())
            sinks.append(sink)

    # 2)产生库所(不能重复)~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    places1, inner_places1, msg_places1 = net1.get_places()
    places2, inner_places2, msg_places2 = net2.get_places()
    places = list(set(places1 + places2))
    inner_places = list(set(inner_places1 + inner_places2))
    msg_places = list(set(msg_places1 + msg_places2))

    # 3)产生资源~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    res_places1, res_property1, req_res_map1, rel_res_map1 = net1.get_res_places(
    )
    res_places2, res_property2, req_res_map2, rel_res_map2 = net2.get_res_places(
    )
    res_places = list(set(res_places1 + res_places2))
    shared_res = set(res_places1).intersection(set(res_places2))
    res_property = {}
    for res, pro in res_property1.items():
        res_property[res] = pro
    # 跳过共享资源
    for res, pro in res_property2.items():
        if res in shared_res:
            continue
        res_property[res] = pro
    # 在产生变迁中构建
    req_res_map = {}
    rel_res_map = {}

    init_res = []
    init_res1 = net1.get_init_res()
    init_res2 = net2.get_init_res()
    for res in init_res1:
        init_res.append(res)
    # 跳过共享资源
    for res in init_res2:
        if res in shared_res:
            continue
        init_res.append(res)

    # 4)产生变迁~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    trans1, rout_trans1, tran_label_map1 = net1.get_trans()
    trans2, rout_trans2, tran_label_map2 = net2.get_trans()
    sync_trans1, sync_trans2 = get_sync_trans(net1, net2)
    trans = []
    tran_label_map = {}
    tran_delay_map = {}

    # a)net1和net2中非同步变迁
    for tran1 in trans1:
        if tran1 not in sync_trans1:
            trans.append(tran1)
            tran_label_map[tran1] = tran_label_map1[tran1]
            # ps:设置合并变迁时间间隔
            print('error:', net1.tran_delay_map[tran1])
            tran_delay_map[tran1] = net1.tran_delay_map[tran1]
            # net1中非同步变迁的请求/释放资源
            req_res_map[tran1] = req_res_map1[tran1]
            rel_res_map[tran1] = rel_res_map1[tran1]
    for tran2 in trans2:
        if tran2 not in sync_trans2:
            trans.append(tran2)
            tran_label_map[tran2] = tran_label_map2[tran2]
            # ps:设置合并变迁时间间隔
            tran_delay_map[tran2] = net2.tran_delay_map[tran2]
            # net2中非同步变迁的请求/释放资源
            req_res_map[tran2] = req_res_map2[tran2]
            rel_res_map[tran2] = rel_res_map2[tran2]

    # b)net1和net2中同步变迁(Note:用于生成同步合并变迁,其中一个变迁可以参加多个同步活动)
    syncMap1 = []
    syncMap2 = []

    print('sync_trans: ', sync_trans1, sync_trans2)

    for sync_tran1 in sync_trans1:

        # sync_trans存储net2中与sync_tran1同步(标号相同)的迁移集
        sync_trans_in_net2 = []

        for sync_tran2 in sync_trans2:
            if tran_label_map1[sync_tran1] == tran_label_map2[sync_tran2]:
                sync_trans_in_net2.append(sync_tran2)

        if sync_tran1 in gen_sync_trans:
            gen_sync_trans.remove(sync_tran1)

        for sync_tran in sync_trans_in_net2:

            if sync_tran in gen_sync_trans:
                gen_sync_trans.remove(sync_tran)

            # 同步变迁Id合并:a_b
            gen_sync_tran = sync_tran1 + '_' + sync_tran
            trans.append(gen_sync_tran)
            tran_label_map[gen_sync_tran] = tran_label_map1[sync_tran1]
            # ps:设置合并变迁时间间隔
            tran_delay_map[gen_sync_tran] = net1.tran_delay_map[sync_tran1]

            # Note:合并同步变迁中多个变迁的请求/释放资源~~~~~~~~~~~~~~~~~~~
            # ps:每个资源库所对应一个资源,若存在相同资源则是共享资源
            req_res_map[gen_sync_tran] = list(
                set(req_res_map1[sync_tran1] + req_res_map2[sync_tran]))
            rel_res_map[gen_sync_tran] = list(
                set(rel_res_map1[sync_tran1] + rel_res_map2[sync_tran]))

            gen_sync_trans.append(gen_sync_tran)

            syncMap1.append([sync_tran1, gen_sync_tran])
            syncMap2.append([sync_tran, gen_sync_tran])

    print('gen_sync_trans: ', gen_sync_trans)
    rout_trans = list(set(rout_trans1 + rout_trans2))

    # 5)产生流关系~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    flows = []
    flows1 = net1.get_flows()
    flows2 = net2.get_flows()

    # ps:要避免重复添加由同步变迁生成的流(由组织内消息流导致)
    for flow in flows1:

        flow_from, flow_to = flow.get_infor()

        if flow_from in sync_trans1:
            merge_trans = get_merge_trans(flow_from, syncMap1)
            for merge_tran in merge_trans:
                if not flow_is_exist(flows, merge_tran, flow_to):
                    flows.append(Flow(merge_tran, flow_to))
        elif flow_to in sync_trans1:
            merge_trans = get_merge_trans(flow_to, syncMap1)
            for merge_tran in merge_trans:
                if not flow_is_exist(flows, flow_from, merge_tran):
                    flows.append(Flow(flow_from, merge_tran))
        else:
            flows.append(flow)

    for flow in flows2:

        flow_from, flow_to = flow.get_infor()

        if flow_from in sync_trans2:
            merge_trans = get_merge_trans(flow_from, syncMap2)
            for merge_tran in merge_trans:
                if not flow_is_exist(flows, merge_tran, flow_to):
                    flows.append(Flow(merge_tran, flow_to))
        elif flow_to in sync_trans2:
            merge_trans = get_merge_trans(flow_to, syncMap2)
            for merge_tran in merge_trans:
                if not flow_is_exist(flows, flow_from, merge_tran):
                    flows.append(Flow(flow_from, merge_tran))
        else:
            flows.append(flow)

    openNet = OpenNet(source, sinks, places, trans, tran_label_map, flows)
    openNet.inner_places = inner_places
    openNet.msg_places = msg_places
    openNet.rout_trans = rout_trans
    openNet.init_res = init_res
    openNet.res_places = res_places
    openNet.res_property = res_property
    openNet.req_res_map = req_res_map
    openNet.rel_res_map = rel_res_map
    openNet.tran_delay_map = tran_delay_map
    return openNet


# 获取同步中合并迁移集
def get_merge_trans(tran, syncMap):
    merge_trans = []
    for item in syncMap:
        if item[0] == tran:
            merge_trans.append(item[1])
    return merge_trans


# 分别获取net1和net2中同步迁移集
def get_sync_trans(net1, net2):
    sync_trans1 = []
    sync_trans2 = []
    trans1, rout_trans1, label_map1 = net1.get_trans()
    trans2, rout_trans2, label_map2 = net2.get_trans()
    for tran1 in trans1:
        # 排除控制变迁
        if tran1 in rout_trans1:
            continue
        if is_sync_tran(tran1, net1, net2):
            sync_trans1.append(tran1)
    for tran2 in trans2:
        # 排除控制变迁
        if tran2 in rout_trans2:
            continue
        if is_sync_tran(tran2, net2, net1):
            sync_trans2.append(tran2)
    return sync_trans1, sync_trans2


# 判断tran1是不是同步变迁
def is_sync_tran(tran1, net1, net2):
    trans1, rout_trans1, tran_label_map1 = net1.get_trans()
    trans2, rout_trans2, tran_label_map2 = net2.get_trans()
    label1 = tran_label_map1[tran1]
    for tran2 in trans2:
        # 排除控制变迁
        if tran2 in rout_trans2:
            continue
        label2 = tran_label_map2[tran2]
        if label1 == label2:
            return True
    return False


# 判断某条流是否存在
def flow_is_exist(flows, flow_from, flow_to):
    for temp_flow in flows:
        temp_flow_from, temp_flow_to = temp_flow.get_infor()
        if temp_flow_from == flow_from and temp_flow_to == flow_to:
            return True
    return False


# 1b.获得合并开放网(异步)-----------------------------------------------
'''
这个方法主要是用于将挖掘获得的网进行合并
'''


def get_compose_net_async(nets):
    if len(nets) == 0:
        print('no bag_nets exist, exit...')
        return
    if len(nets) == 1:
        return nets[0]
    else:
        net = compose_two_nets_async(nets[0], nets[1])
        for i in range(2, len(nets)):
            net = compose_two_nets_async(net, nets[i])
        return net


# 异步合并两个开放网
def compose_two_nets_async(net1: OpenNet, net2: OpenNet):

    # 1)产生源和终止标识~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    source1, sinks1 = net1.get_start_ends()
    source2, sinks2 = net2.get_start_ends()
    # ps:避免重复添加消息或者资源(消息和资源可以初始存在)
    source = Marking(list(set(source1.get_infor() + source2.get_infor())))
    sinks = []
    for sink1 in sinks1:
        for sink2 in sinks2:
            sink = Marking(sink1.get_infor() + sink2.get_infor())
            sinks.append(sink)

    # 2)产生库所(不能重复)~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    places1, inner_places1, msg_places1 = net1.get_places()
    places2, inner_places2, msg_places2 = net2.get_places()
    places = list(set(places1 + places2))
    inner_places = list(set(inner_places1 + inner_places2))
    msg_places = list(set(msg_places1 + msg_places2))

    # 3)产生资源~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    res_places = list(set(net1.res_places + net2.res_places))

    # 4)产生变迁~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    trans1, rout_trans1, tran_label_map1 = net1.get_trans()
    trans2, rout_trans2, tran_label_map2 = net2.get_trans()
    trans = []
    tran_label_map = {}
    # tran_delay_map = {}

    # net1和net2中变迁
    for tran1 in trans1:
        trans.append(tran1)
        tran_label_map[tran1] = tran_label_map1[tran1]
        # ps:设置合并变迁时间间隔
        # tran_delay_map[tran1] = net1.tran_delay_map[tran1]
    for tran2 in trans2:
        if tran2 in trans1:  #ps:跳过重复同步变迁
            continue
        trans.append(tran2)
        tran_label_map[tran2] = tran_label_map2[tran2]
        # ps:设置合并变迁时间间隔
        # tran_delay_map[tran2] = net2.tran_delay_map[tran2]

    # 5)产生流关系(避免添加由同步变迁导致的重复流)~~~~~~~~~~~~~
    flows = []
    flows1 = net1.get_flows()
    for flow in flows1:
        flow_from, flow_to = flow.get_infor()
        if not flow_is_exist(flows, flow_from, flow_to):
            flows.append(flow)
    flows2 = net2.get_flows()
    for flow in flows2:
        flow_from, flow_to = flow.get_infor()
        if not flow_is_exist(flows, flow_from, flow_to):
            flows.append(flow)

    openNet = OpenNet(source, sinks, places, trans, tran_label_map, flows)
    openNet.inner_places = inner_places
    openNet.msg_places = msg_places
    openNet.res_places = res_places
    # openNet.tran_delay_map = tran_delay_map
    return openNet





