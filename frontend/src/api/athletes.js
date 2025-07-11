import axios from "axios";

const API_URL = "http://localhost:8000/athletes";

export const fetchAthletes = () => axios.get(API_URL);
export const createAthlete = (data) => axios.post(API_URL, data);
