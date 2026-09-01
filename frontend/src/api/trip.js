import axios from 'axios';

const apiClient = axios.create({
    baseURL: 'http://127.0.0.1:8000/api/v1',
    timeout: 60000,
    headers: {
        'Content-Type': 'application/json'
    }
});

export const generateTripApi = async (params) => {
    const response = await apiClient.post('/trip/generate', params);
    return response.data;
};