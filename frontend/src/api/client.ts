import axios, {
  AxiosError,
} from 'axios';

interface R<T> {
  success: boolean;
  code: number;
  message: string;
  data: T | null;
}

export class ApiError extends Error {
  readonly code: number;

  constructor(code: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
  }
}

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 30_000,
});

client.interceptors.response.use(
  (response) => {
    const envelope = response.data as R<unknown>;
    if (!envelope.success || envelope.data === null) {
      throw new ApiError(envelope.code, envelope.message);
    }
    // Axios 固定要求响应拦截器返回 AxiosResponse，但本项目在请求方法的
    // 第二个泛型参数中声明了解包后的业务数据类型。
    return envelope.data as typeof response;
  },
  (error: AxiosError<R<unknown>>): Promise<never> => {
    const envelope = error.response?.data;
    if (envelope) {
      return Promise.reject(new ApiError(envelope.code, envelope.message));
    }
    return Promise.reject(new ApiError(0, error.message || '无法连接 TokenTide API'));
  },
);

export default client;
