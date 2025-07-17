import axios from 'axios';

const axiosSession = axios.create({
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': '{{ csrf_token }}'
  }
});

axiosSession.interceptors.request.use((config) => {
  const token = window.cookieStore.get('csrftoken');
  if (token) {
    config.headers['X-CSRFToken'] = token.value;
  }
  return config;
});

export default axiosSession;
