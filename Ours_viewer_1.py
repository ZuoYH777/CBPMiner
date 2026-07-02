# coding=gbk
from pywebio.input import input_group, file_upload, actions
from pywebio.output import put_image, put_markdown, use_scope, clear, put_text, put_info, put_success
import Ours_1 as ou
import os
import mining_utils as mu

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'file_server')

# 清空服务器文件夹
def del_files(path):
    if not os.path.exists(path):
        os.makedirs(path)
        return
    ls = os.listdir(path)
    for i in ls:
        c_path = os.path.join(path, i)
        if os.path.isdir(c_path):
            del_files(c_path)
        else:
            os.remove(c_path)


# 1.利用scope来显示产生的通路,并获取输入网和数据操作-----------------
with use_scope('Top'):
    # 标题加粗大写
    put_markdown(r""" # <center>CBP Miner """).show()
    # 插入分割线
    # put_markdown(r""" ___ """).show()
    with use_scope('output'):
        put_markdown(r""" </br> """).show()
        put_info('The discovered CBP and CDs will be presented here.')
        put_text('')
        put_image('')

    info = input_group('Request form', [
        file_upload("Please upload an event log in CSV format:",
                    name='log',
                    placeholder='Choose file',
                    accept=".csv,.txt,.pdf,.jpg",
                    required=True),
        actions('', [
            {
                'label': 'Generate',
                'value': 'generate'
            },
        ],
                name='action'),
    ])

# 2.通过循环接收输入,然后输出产生的通路----------------------------
while info is not None:
    if info['action'] == 'generate':

        # a.清空本地服务器文件夹
        del_files(BASE_DIR)
        # b.清空显示通路范围
        clear(scope='Top')

        # c.先写入文件服务器
        log_name = info['log'].get('filename')
        log_path = os.path.join(BASE_DIR, log_name)
        with open(log_path, mode='wb') as f:
            f.write(info['log'].get('content'))

        # d.发现网和CDs
        df = mu.csv_to_df(log_path)
        non_duplicate_df, nets, comp_net = ou.CCHP_Discovery(df)

        cases = mu.gen_cases(non_duplicate_df)
        kernel = ou.gen_kernel(cases, comp_net)

        unstable_tasks = ou.get_unstable_tasks(kernel, comp_net)
        print('unstable_tasks:', unstable_tasks)

        # ps:将kernel需要转化为LTS
        kernel = kernel.rg_to_lts()[0]
        # kernel.lts_to_dot()
        CDs = ou.gen_CDs(nets, kernel, unstable_tasks)

        # e.产生jpg图像
        net_path = os.path.join(BASE_DIR, 'comp_net')
        comp_net.net_to_dot(net_path, False)
        for i, CD in enumerate(CDs):
            cd_path = os.path.join(BASE_DIR, 'CD{}'.format(i))
            CD.lts_to_dot_name(cd_path)

        # Note:设置读取二进制的rb模式
        img = open(net_path + '.jpg', 'rb').read()

        # f. display results
        put_markdown(r""" # <center>CBP Miner """, scope='Top').show()
        put_success('Discovered CBP:', scope='Top')
        put_image(img, scope='Top')
        put_markdown(r""" <br/> """, scope='Top').show()
        put_markdown(r""" <br/> """, scope='Top').show()
        put_success(' CDs ({})'.format(len((CDs))), scope='Top')
        for index in range(0, len(CDs)):
            cd_path = os.path.join(BASE_DIR, 'CD{}.gv'.format(index))
            # Note:设置读取二进制的rb模式
            img = open(cd_path + '.jpg', 'rb').read()
            put_image(img, scope='Top')
        # g.继续接收输入
        info = input_group('Request form', [
            file_upload("Please upload an event log in CSV format:",
                        name='log',
                        placeholder='Choose file',
                        accept=".csv,.txt,.pdf,.jpg",
                        required=True),
            actions('', [
                {
                    'label': 'Generate',
                    'value': 'generate'
                },
            ],
                    name='action'),
        ])
