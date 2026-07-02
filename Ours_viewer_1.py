# coding=gbk
from pywebio.input import input_group, file_upload, actions
from pywebio.output import put_image, put_markdown, use_scope, clear, put_text, put_info, put_success
import Ours_1 as ou
import os
import mining_utils as mu


# 清空服务器文件夹
def del_files(path):
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
        del_files('/Users/moqi/VSCodeProjects/file server')
        # b.清空显示通路范围
        clear(scope='Top')

        # c.先写入文件服务器
        log_name = info['log'].get('filename')
        log_path = '/Users/moqi/VSCodeProjects/file server/{}'.format(log_name)
        with open(log_path, mode='wb') as f:
            f.write(info['log'].get('content'))

        # d.发现网和CDs
        non_duplicate_df, nets, comp_net = mu.CCHP_Discovery(log_path)

        cases = mu.gen_cases(non_duplicate_df)
        kernel = ou.gen_kernel(cases, comp_net)

        unstable_tasks = ou.get_unstable_tasks(kernel, comp_net)
        print('unstable_tasks:', unstable_tasks)

        # ps:将kernel需要转化为LTS
        kernel = kernel.rg_to_lts()[0]
        # kernel.lts_to_dot()
        CDs = ou.gen_CDs(nets, kernel, unstable_tasks)

        # e.产生jpg图像
        net_path = '/Users/moqi/VSCodeProjects/file server/{}'.format(
            'comp_net')
        comp_net.net_to_dot(net_path, False)
        for i, CD in enumerate(CDs):
            cd_path = '/Users/moqi/VSCodeProjects/file server/CD{}'.format(i)
            CD.lts_to_dot_name(cd_path)

        # Note:设置读取二进制的rb模式
        img = open(net_path + '.jpg', 'rb').read()

        with use_scope('Top'):
            # 标题加粗大写居中
            put_markdown(r""" # <center>CBP Miner """).show()
            # f.将图像显示在范围中
            with use_scope('output'):
                put_success('Discovered CBP:')
                put_image(img)
                # 空两行
                put_markdown(r""" <br/> """).show()
                put_markdown(r""" <br/> """).show()
                put_success(' CDs ({})'.format(len((CDs))))
                for index in range(0, len(CDs)):
                    cd_path = '/Users/moqi/VSCodeProjects/file server/CD{}.gv'.format(
                        index)
                    # Note:设置读取二进制的rb模式
                    img = open(cd_path + '.jpg', 'rb').read()
                    put_image(img)
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
