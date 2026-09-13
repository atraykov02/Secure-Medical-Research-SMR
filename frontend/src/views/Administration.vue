<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, errorText } from '../api'
import type { Organization, User, Role } from '../types'
import { PageHead } from '../components/Ui.vue'
import PasswordInput from '../components/PasswordInput.vue'
import { tr } from '../i18n'
import { CircleCheck, Pencil, Plus, RefreshCw, Trash2, X } from 'lucide-vue-next'
import { toast } from '../stores/toast'

const tab = ref<'orgs' | 'users'>('orgs')
const orgs = ref<Organization[]>([]), users = ref<User[]>([])
const showOrg = ref(false), showUser = ref(false)
const editingOrgId = ref<string | null>(null), editingUserId = ref<string | null>(null)
const deleteTarget = ref<{ type: 'organization' | 'user'; id: string; name: string } | null>(null)
const deleteError = ref(''), deleting = ref(false)
const checkingOrgId = ref<string | null>(null)
const orgForm = reactive({ name: '', type: 'HOSPITAL', node_url: '' })
const userForm = reactive({ first_name: '', last_name: '', email: '', password: '', role: 'ORG_ADMIN' as Role, organization_id: '' })

async function load() {
  [orgs.value, users.value] = await Promise.all([
    api.get('/organizations').then(r => r.data),
    api.get('/users').then(r => r.data)
  ])
}
onMounted(load)

function openOrgCreate() {
  editingOrgId.value = null
  Object.assign(orgForm, { name: '', type: 'HOSPITAL', node_url: '' })
  showOrg.value = true
}
function openOrgEdit(o: Organization) {
  editingOrgId.value = o.id
  Object.assign(orgForm, { name: o.name, type: o.type, node_url: o.node_url || '' })
  showOrg.value = true
}
async function saveOrg() {
  try {
    const payload = { name: orgForm.name, type: orgForm.type, node_url: orgForm.node_url || null }
    if (editingOrgId.value) await api.patch(`/organizations/${editingOrgId.value}`, payload)
    else await api.post('/organizations', payload)
    Object.assign(orgForm, { name: '', type: 'HOSPITAL', node_url: '' })
    showOrg.value = false
    toast.success(editingOrgId.value ? 'Организацията е редактирана.' : 'Организацията е регистрирана като неактивна. Проверете връзката и я активирайте.')
    editingOrgId.value = null
    await load()
  } catch (e) {
    toast.error(errorText(e))
  }
}

function openUserCreate() {
  editingUserId.value = null
  Object.assign(userForm, { first_name: '', last_name: '', email: '', password: '', role: 'ORG_ADMIN', organization_id: '' })
  showUser.value = true
}
function openUserEdit(u: User) {
  editingUserId.value = u.id
  Object.assign(userForm, { first_name: u.first_name, last_name: u.last_name, email: u.email, password: '', role: u.role, organization_id: u.organization_id || '' })
  showUser.value = true
}
async function saveUser() {
  try {
    const payload: Record<string, unknown> = { ...userForm, organization_id: userForm.organization_id || null }
    if (editingUserId.value && !userForm.password) delete payload.password
    if (editingUserId.value) await api.patch(`/users/${editingUserId.value}`, payload)
    else await api.post('/users', payload)
    Object.assign(userForm, { first_name: '', last_name: '', email: '', password: '', role: 'ORG_ADMIN', organization_id: '' })
    showUser.value = false
    toast.success(editingUserId.value ? 'Потребителят е редактиран.' : 'Потребителят е създаден.')
    editingUserId.value = null
    await load()
  } catch (e) {
    toast.error(errorText(e))
  }
}

function requestDelete(type: 'organization' | 'user', id: string, name: string) {
  deleteError.value = ''
  deleteTarget.value = { type, id, name }
}
async function confirmDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  deleteError.value = ''
  try {
    const target = deleteTarget.value
    await api.delete(target.type === 'organization' ? `/organizations/${target.id}` : `/users/${target.id}`)
    toast.success(target.type === 'organization' ? 'Организацията е изтрита.' : 'Потребителят е изтрит.')
    deleteTarget.value = null
    await load()
  } catch (e) { deleteError.value = errorText(e) }
  finally { deleting.value = false }
}

async function toggleOrg(o: Organization) {
  try {
    await api.patch(`/organizations/${o.id}`, { is_active: !o.is_active })
    toast.info(o.is_active ? 'Организацията е деактивирана.' : 'Организацията е активирана.')
    await load()
  } catch (e) {
    toast.error(errorText(e))
  }
}

async function verifyOrg(o: Organization) {
  checkingOrgId.value = o.id
  try {
    const { data } = await api.post(`/organizations/${o.id}/verify`)
    toast.success(`Връзката е успешна: ${data.organization_name}, възел P${data.participant_index}.`)
    await load()
  } catch (e) {
    toast.error(errorText(e))
  } finally {
    checkingOrgId.value = null
  }
}

async function toggleUser(u: User) {
  try {
    await api.patch(`/users/${u.id}`, { is_active: !u.is_active })
    toast.info(u.is_active ? 'Потребителят е деактивиран.' : 'Потребителят е активиран.')
    await load()
  } catch (e) {
    toast.error(errorText(e))
  }
}

function tabButtonClass(value: 'orgs' | 'users'): string {
  if (tab.value === value) return 'border-pine-600 text-pine-700'
  return 'border-transparent text-mist hover:text-ink'
}

function formActionLabel(editingId: string | null): string {
  if (editingId) return 'Запази'
  return 'Създай'
}

function organizationTypeLabel(type: string): string {
  if (type === 'HOSPITAL') return 'Болница'
  if (type === 'LABORATORY') return 'Лаборатория'
  return 'Изследователски център'
}

function participantLabel(index: number | null | undefined): string {
  if (index) return `P${index}`
  return '—'
}

function activeStatusClass(isActive: boolean): string {
  if (isActive) return 'bg-pine-500'
  return 'bg-brick'
}

function organizationStatusLabel(isActive: boolean): string {
  if (isActive) return 'Активна'
  return 'Неактивна'
}

function userStatusLabel(isActive: boolean): string {
  if (isActive) return 'Активен'
  return 'Неактивен'
}

function verificationIconClass(organizationId: string): string {
  if (checkingOrgId.value === organizationId) return 'animate-spin'
  return ''
}

function organizationToggleLabel(isActive: boolean): string {
  if (isActive) return 'Деактивирай'
  return 'Активирай'
}

function userToggleLabel(isActive: boolean): string {
  if (isActive) return 'Деактивирай'
  return 'Активирай'
}

function userPasswordLabel(): string {
  if (editingUserId.value) return 'Парола (оставете празна без промяна)'
  return 'Парола'
}

function deleteTargetTypeLabel(type: 'organization' | 'user'): string {
  if (type === 'organization') return 'организация'
  return 'потребител'
}

function deleteButtonLabel(): string {
  if (deleting.value) return 'Изтриване…'
  return 'Изтрий'
}
</script>

<template>
  <PageHead eyebrow="Системно управление" title="Администрация" description="Управление на регистрираните организации, потребителите и достъпа до платформата." />

  <div class="mb-5 flex gap-6 border-b border-line">
    <button
      class="-mb-px flex cursor-pointer items-center gap-2 border-b-2 px-1 pb-2.5 text-sm font-medium transition"
      :class="tabButtonClass('orgs')"
      @click="tab = 'orgs'"
    >
      Организации
      <b class="rounded-full bg-paper px-2 py-0.5 text-[11px]">{{ orgs.length }}</b>
    </button>
    <button
      class="-mb-px flex cursor-pointer items-center gap-2 border-b-2 px-1 pb-2.5 text-sm font-medium transition"
      :class="tabButtonClass('users')"
      @click="tab = 'users'"
    >
      Потребители
      <b class="rounded-full bg-paper px-2 py-0.5 text-[11px]">{{ users.length }}</b>
    </button>
  </div>

  <section v-if="tab === 'orgs'" class="panel rise">
    <div class="flex flex-wrap items-center justify-between gap-4 px-6 pb-4 pt-5">
      <h2 class="text-base font-bold">Регистрирани организации</h2>
      <button class="btn-primary" @click="openOrgCreate"><Plus :size="16" />Добави организация</button>
    </div>

    <div class="mx-6 mb-5 rounded-xl border border-pine-200 bg-pine-50/60 px-4 py-3 text-xs leading-5 text-pine-900">
      <b>Присъединяване на болница:</b> въведете адреса на предварително инсталирания Hospital Node. Организацията се създава неактивна. След успешна удостоверена проверка на връзката може да я активирате за участие в проучвания.
    </div>

    <form v-if="showOrg" class="grid items-end gap-3 border-t border-line bg-paper/60 px-6 py-4 sm:grid-cols-[1.2fr_1fr_1.8fr_auto_auto]" @submit.prevent="saveOrg">
      <label class="field !my-0">Име<input v-model="orgForm.name" required></label>
      <label class="field !my-0">Тип
        <select v-model="orgForm.type">
          <option value="HOSPITAL">Болница</option>
          <option value="LABORATORY">Лаборатория</option>
          <option value="RESEARCH_CENTER">Изследователски център</option>
        </select>
      </label>
      <label class="field !my-0">Адрес на организацията (node)<input v-model="orgForm.node_url" placeholder="http://hospital-d:8000"></label>
      <button type="button" class="btn-secondary" @click="showOrg = false; editingOrgId = null">Отказ</button>
      <button class="btn-primary">{{ formActionLabel(editingOrgId) }}</button>
    </form>

    <div class="overflow-x-auto">
      <table class="table-base">
        <thead>
          <tr><th>Организация</th><th>Тип</th><th>Адрес на организацията (node)</th><th>Възел</th><th>Статус</th><th>Действие</th></tr>
        </thead>
        <tbody>
          <tr v-for="o in orgs" :key="o.id">
            <td><b class="text-[13px]">{{ o.name }}</b></td>
            <td class="text-[13px]">{{ organizationTypeLabel(o.type) }}</td>
            <td><code class="font-mono text-xs text-ink/70">{{ o.node_url || 'Не е конфигуриран' }}</code></td>
            <td class="font-mono text-xs">{{ participantLabel(o.participant_index) }}</td>
            <td><span class="inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-medium text-ink/80"><i class="size-1.5 rounded-full" :class="activeStatusClass(o.is_active)"></i>{{ organizationStatusLabel(o.is_active) }}</span></td>
            <td><div class="flex items-center gap-1.5"><button class="btn-secondary !px-2.5 !py-1.5 !text-xs" :disabled="checkingOrgId === o.id || !o.node_url" @click="verifyOrg(o)"><RefreshCw :size="13" :class="verificationIconClass(o.id)" />Провери</button><button class="btn-secondary !px-2.5 !py-1.5 !text-xs" @click="toggleOrg(o)"><CircleCheck v-if="!o.is_active" :size="13" />{{ organizationToggleLabel(o.is_active) }}</button><button class="btn-secondary !p-2" aria-label="Редактирай организацията" @click="openOrgEdit(o)"><Pencil :size="14" /></button><button class="btn-danger !p-2" aria-label="Изтрий организацията" @click="requestDelete('organization', o.id, o.name)"><Trash2 :size="14" /></button></div></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <section v-else class="panel rise">
    <div class="flex flex-wrap items-center justify-between gap-4 px-6 pb-4 pt-5">
      <h2 class="text-base font-bold">Потребители и роли</h2>
      <button class="btn-primary" @click="openUserCreate"><Plus :size="16" />Добави потребител</button>
    </div>

    <form v-if="showUser" class="grid items-end gap-3 border-t border-line bg-paper/60 px-6 py-4 sm:grid-cols-3" @submit.prevent="saveUser">
      <label class="field !my-0">Име<input v-model="userForm.first_name" required></label>
      <label class="field !my-0">Фамилия<input v-model="userForm.last_name" required></label>
      <label class="field !my-0">Имейл<input v-model="userForm.email" type="email" required></label>
      <label class="field !my-0">{{ userPasswordLabel() }}<PasswordInput v-model="userForm.password" :minlength="8" :required="!editingUserId" autocomplete="new-password" /></label>
      <label class="field !my-0">Роля
        <select v-model="userForm.role">
          <option value="RESEARCHER">Изследовател</option>
          <option value="ORG_ADMIN">Администратор на организация</option>
          <option value="SYSTEM_ADMIN">Системен администратор</option>
        </select>
      </label>
      <label class="field !my-0">Организация
        <select v-model="userForm.organization_id">
          <option value="">Без организация</option>
          <option v-for="o in orgs" :key="o.id" :value="o.id">{{ o.name }}</option>
        </select>
      </label>
      <div class="flex justify-end gap-2 sm:col-start-3"><button type="button" class="btn-secondary" @click="showUser = false; editingUserId = null">Отказ</button><button class="btn-primary">{{ formActionLabel(editingUserId) }}</button></div>
    </form>

    <div class="overflow-x-auto">
      <table class="table-base">
        <thead>
          <tr><th>Потребител</th><th>Имейл</th><th>Роля</th><th>Организация</th><th>Статус</th><th>Действие</th></tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td><b class="text-[13px]">{{ u.first_name }} {{ u.last_name }}</b></td>
            <td class="text-[13px] text-mist">{{ u.email }}</td>
            <td class="text-[13px]">{{ tr(u.role) }}</td>
            <td class="text-[13px]">{{ orgs.find(o => o.id === u.organization_id)?.name || 'Без организация' }}</td>
            <td><span class="inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-medium text-ink/80"><i class="size-1.5 rounded-full" :class="activeStatusClass(u.is_active)"></i>{{ userStatusLabel(u.is_active) }}</span></td>
            <td><div class="flex items-center gap-1.5"><button class="btn-secondary !px-2.5 !py-1.5 !text-xs" @click="toggleUser(u)">{{ userToggleLabel(u.is_active) }}</button><button class="btn-secondary !p-2" aria-label="Редактирай потребителя" @click="openUserEdit(u)"><Pencil :size="14" /></button><button class="btn-danger !p-2" aria-label="Изтрий потребителя" @click="requestDelete('user', u.id, `${u.first_name} ${u.last_name}`)"><Trash2 :size="14" /></button></div></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <Teleport to="body">
    <div v-if="deleteTarget" class="fixed inset-0 z-50 grid place-items-center bg-pine-950/55 p-4 backdrop-blur-sm" @click.self="deleteTarget = null">
      <section class="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="admin-delete-title">
        <header class="flex items-center justify-between border-b border-line px-6 py-5"><h2 id="admin-delete-title" class="text-lg font-bold">Изтриване на {{ deleteTargetTypeLabel(deleteTarget.type) }}</h2><button class="grid size-9 place-items-center rounded-lg text-mist hover:bg-paper" :disabled="deleting" aria-label="Затвори" @click="deleteTarget = null"><X :size="20" /></button></header>
        <div class="px-6 py-5"><p class="text-sm">Сигурни ли сте, че искате да изтриете <b>{{ deleteTarget.name }}</b>?</p><p class="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">Действието е необратимо. Свързани с проучвания или историята записи няма да могат да бъдат изтрити.</p><div v-if="deleteError" class="mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">{{ deleteError }}</div></div>
        <footer class="flex justify-end gap-2 border-t border-line px-6 py-4"><button class="btn-secondary" :disabled="deleting" @click="deleteTarget = null">Отказ</button><button class="btn-danger" :disabled="deleting" @click="confirmDelete"><Trash2 :size="16" />{{ deleteButtonLabel() }}</button></footer>
      </section>
    </div>
  </Teleport>
</template>
