import axios from "axios";
const request = axios.create({

    baseURL: "http://geek.itheima.net/v1_0"
    ,timeout: 5000
})
request.interceptors.request.use((config)=>{
    return config;
},(err)=>{
    return Promise.reject(err);
})
request.interceptors.response.use((response)=>{
     // 2xx 范围内的状态码都会触发该函数。
    // 对响应数据做点什么
    return response.data;
},(err)=>{
    // 超出 2xx 范围的状态码都会触发该函数。
    // 对响应错误做点什么
    return Promise.reject(err);
})
export default request;