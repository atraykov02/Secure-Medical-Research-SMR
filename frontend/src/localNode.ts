import axios from 'axios'
import { api } from './api'
import type { HospitalAccess, LocalMedicalCatalog, LocalPatients, LocalPatientWrite, LocalStudyInput, Study } from './types'

export async function hospitalAccess(): Promise<HospitalAccess> {
  return (await api.get<HospitalAccess>('/organizations/me/local-access')).data
}

export type LocalPatientFilters = {
  search?: string; min_age?: number; max_age?: number; sex?: string;
  disease?: string; variant?: string; therapy?: string; response?: string
}

export async function getLocalPatients(page = 1, pageSize = 20, filters: LocalPatientFilters = {}): Promise<LocalPatients> {
  const access = await hospitalAccess()
  return (await axios.get<LocalPatients>(`${access.node_url}/api/local/patients`, {
    params: { page, page_size: pageSize, ...filters },
    headers: { Authorization: `Bearer ${access.access_token}` },
  })).data
}

export async function getLocalStudyInput(study: Study): Promise<LocalStudyInput> {
  const access = (await api.get<HospitalAccess>(`/studies/${study.id}/local-access`)).data
  return (await axios.post<LocalStudyInput>(
    `${access.node_url}/api/local/studies/${study.id}/input`,
    { analysis_type: study.analysis_type, criteria: study.criteria },
    { headers: { Authorization: `Bearer ${access.access_token}` } },
  )).data
}

async function localPatientRequest<T>(method: 'get'|'post'|'put'|'delete', path: string, data?: unknown): Promise<T> {
  const access = await hospitalAccess()
  return (await axios.request<T>({
    method, url: `${access.node_url}/api/local/patients${path}`,
    data, headers: { Authorization: `Bearer ${access.access_token}` },
  })).data
}

export const getLocalPatient = (identifier: string) =>
  localPatientRequest<LocalPatientWrite>('get', `/${encodeURIComponent(identifier)}`)
export async function getLocalMedicalCatalog(): Promise<LocalMedicalCatalog> {
  const access = await hospitalAccess()
  return (await axios.get<LocalMedicalCatalog>(`${access.node_url}/api/local/catalog`, {
    headers: { Authorization: `Bearer ${access.access_token}` },
  })).data
}

export async function createLocalCatalogItem(kind: 'diseases'|'variants'|'therapies'|'responses', payload: unknown): Promise<void> {
  const access = await hospitalAccess()
  await axios.post(`${access.node_url}/api/local/catalog/${kind}`, payload, {
    headers: { Authorization: `Bearer ${access.access_token}` },
  })
}

export async function updateLocalCatalogItem(kind: 'diseases'|'variants'|'therapies'|'responses', code: string, payload: unknown): Promise<void> {
  const access = await hospitalAccess()
  await axios.put(`${access.node_url}/api/local/catalog/${kind}/${encodeURIComponent(code)}`, payload, {
    headers: { Authorization: `Bearer ${access.access_token}` },
  })
}

export async function deleteLocalCatalogItem(kind: 'diseases'|'variants'|'therapies'|'responses', code: string): Promise<void> {
  const access = await hospitalAccess()
  await axios.delete(`${access.node_url}/api/local/catalog/${kind}/${encodeURIComponent(code)}`, {
    headers: { Authorization: `Bearer ${access.access_token}` },
  })
}
export const createLocalPatient = (payload: LocalPatientWrite) =>
  localPatientRequest<LocalPatientWrite>('post', '', payload)
export const updateLocalPatient = (identifier: string, payload: LocalPatientWrite) =>
  localPatientRequest<LocalPatientWrite>('put', `/${encodeURIComponent(identifier)}`, payload)
export const deleteLocalPatient = (identifier: string) =>
  localPatientRequest<void>('delete', `/${encodeURIComponent(identifier)}`)
