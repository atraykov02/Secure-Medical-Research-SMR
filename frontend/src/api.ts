import axios from 'axios'
export const api=axios.create({baseURL:import.meta.env.VITE_API_BASE_URL||'/api'})
api.interceptors.request.use(c=>{const token=localStorage.getItem('precisionmpc_token');if(token)c.headers.Authorization=`Bearer ${token}`;return c})
api.interceptors.response.use(r=>r,e=>{if(e.response?.status===401){localStorage.removeItem('precisionmpc_token');if(location.pathname!='/login')location.assign('/login')}return Promise.reject(e)})
export function errorText(e:unknown){if(axios.isAxiosError(e)){const d=String(e.response?.data?.detail||'');if(e.response?.status===401)return'Невалиден имейл адрес или парола.';if(e.response?.status===403)return'Нямате права за това действие.';return d||'Възникна грешка при връзката със сървъра.'}return'Възникна неочаквана грешка.'}
