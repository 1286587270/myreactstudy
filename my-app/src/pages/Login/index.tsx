import {Card,Form,Input,Button} from 'antd'
const Login = ()=>{
    const onFinish = (values:any)=>{
        console.log(values)
    }
    return (
        <div><Card>
            <Form validateTrigger={['onBlur']} onFinish={onFinish}>
                <Form.Item name="username" rules={[{required:true,message:'请输入用户名'}]}>
                    <Input placeholder="请输入用户名"/>
                </Form.Item>
                <Form.Item name="password">
                    <Input placeholder="请输入密码" maxLength={8}/>
                </Form.Item>
                <Form.Item>
                    <Button type="primary" htmlType="submit">
                        登录
                    </Button>
                </Form.Item>
                </Form>
            </Card></div>
    )
}
export default Login;