import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ShieldPlus, ShieldMinus, UserCheck, UserX, Users } from 'lucide-react'

import {
  assignRole,
  getRoles,
  getUsers,
  revokeRole,
  updateUserActive,
} from '../api/client'
import { useAuthStore } from '../stores/authStore'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '../components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table'
import { Alert, AlertDescription } from '../components/ui/alert'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog'
import EmptyState from '../components/EmptyState'
import LoadingState from '../components/LoadingState'
import { PageHeader } from '../components/PageContainer'
import { toast } from '../hooks/use-toast'

const LIMIT = 20

export default function UsersPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const currentUser = useAuthStore((s) => s.user)
  const [offset, setOffset] = useState(0)
  const [assignTarget, setAssignTarget] = useState(null)

  const usersQuery = useQuery({
    queryKey: ['users', { limit: LIMIT, offset }],
    queryFn: () => getUsers({ limit: LIMIT, offset }).then((r) => r.data),
    keepPreviousData: true,
  })

  const rolesQuery = useQuery({
    queryKey: ['roles'],
    queryFn: () => getRoles().then((r) => r.data),
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['users'] })

  const activeMutation = useMutation({
    mutationFn: ({ id, isActive }) => updateUserActive(id, isActive),
    onSuccess: () => {
      invalidate()
      toast({ description: t('users.updated', { defaultValue: 'User updated' }) })
    },
    onError: (err) =>
      toast({
        variant: 'destructive',
        description: err.response?.data?.detail || t('errors.serverError'),
      }),
  })

  const assignMutation = useMutation({
    mutationFn: ({ userId, roleId }) => assignRole(userId, roleId),
    onSuccess: () => {
      invalidate()
      setAssignTarget(null)
      toast({ description: t('users.roleAssigned', { defaultValue: 'Role assigned' }) })
    },
    onError: (err) =>
      toast({
        variant: 'destructive',
        description: err.response?.data?.detail || t('errors.serverError'),
      }),
  })

  const revokeMutation = useMutation({
    mutationFn: ({ userId, roleId }) => revokeRole(userId, roleId),
    onSuccess: () => {
      invalidate()
      toast({ description: t('users.roleRevoked', { defaultValue: 'Role revoked' }) })
    },
    onError: (err) =>
      toast({
        variant: 'destructive',
        description: err.response?.data?.detail || t('errors.serverError'),
      }),
  })

  const items = usersQuery.data?.items ?? []
  const total = usersQuery.data?.total ?? 0
  const allRoles = rolesQuery.data?.items ?? []

  const handlePrev = () => setOffset(Math.max(0, offset - LIMIT))
  const handleNext = () => {
    if (offset + LIMIT < total) setOffset(offset + LIMIT)
  }

  const handleToggleActive = (user) => {
    if (user.id === currentUser?.id) {
      toast({
        variant: 'destructive',
        description: t('users.cannotToggleSelf', { defaultValue: 'You cannot deactivate your own account' }),
      })
      return
    }
    activeMutation.mutate({ id: user.id, isActive: !user.is_active })
  }

  const handleRevoke = (user, role) => {
    if (
      user.id === currentUser?.id
      && role.key === 'admin'
      && window.confirm(t('users.revokeAdminConfirm', { defaultValue: 'Revoke your own admin role?' }))
    ) {
      revokeMutation.mutate({ userId: user.id, roleId: role.id })
    } else if (user.id !== currentUser?.id || role.key !== 'admin') {
      revokeMutation.mutate({ userId: user.id, roleId: role.id })
    }
  }

  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + LIMIT, total)

  return (
    <>
      <PageHeader
        title={t('users.title')}
        description={t('users.subtitle')}
      />

      {usersQuery.isError && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>
            {usersQuery.error?.response?.data?.detail || t('errors.serverError')}
          </AlertDescription>
        </Alert>
      )}

      {usersQuery.isLoading ? (
        <LoadingState variant="skeleton" count={5} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Users}
          title={t('users.empty')}
          description={t('users.emptyDescription', { defaultValue: 'No users yet' })}
        />
      ) : (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">
              {t('users.title')} ({total})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('users.username')}</TableHead>
                  <TableHead>{t('users.email')}</TableHead>
                  <TableHead>{t('users.roles')}</TableHead>
                  <TableHead>{t('users.status')}</TableHead>
                  <TableHead className="text-right">
                    {t('common.actions')}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell className="font-medium">{user.username}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {user.email}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap items-center gap-1">
                        {(user.roles || []).map((role) => (
                          <Badge
                            key={role.id}
                            variant={role.key === 'admin' ? 'default' : 'secondary'}
                            className="gap-1"
                          >
                            {role.key}
                            <button
                              type="button"
                              onClick={() => handleRevoke(user, role)}
                              className="ml-1 inline-flex items-center"
                              aria-label={`revoke ${role.key}`}
                              title={t('users.revokeRole', { defaultValue: 'Revoke role' })}
                            >
                              <ShieldMinus className="h-3 w-3" />
                            </button>
                          </Badge>
                        ))}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setAssignTarget(user)}
                          disabled={rolesQuery.isLoading}
                        >
                          <ShieldPlus className="mr-1 h-3 w-3" />
                          {t('users.assignRole')}
                        </Button>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={user.is_active ? 'success' : 'secondary'}>
                        {user.is_active
                          ? t('users.active')
                          : t('users.inactive')}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleToggleActive(user)}
                        disabled={user.id === currentUser?.id}
                      >
                        {user.is_active ? (
                          <>
                            <UserX className="mr-1 h-3 w-3" />
                            {t('users.deactivate')}
                          </>
                        ) : (
                          <>
                            <UserCheck className="mr-1 h-3 w-3" />
                            {t('users.activate')}
                          </>
                        )}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {total > LIMIT && (
              <div className="mt-4 flex items-center justify-between border-t pt-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePrev}
                  disabled={offset === 0}
                >
                  {t('common.back')}
                </Button>
                <span className="text-sm text-muted-foreground">
                  {t('experiments.list.range', { from, to, total })}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleNext}
                  disabled={offset + LIMIT >= total}
                >
                  {t('common.next')}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Dialog
        open={Boolean(assignTarget)}
        onOpenChange={(open) => !open && setAssignTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('users.assignRole')}</DialogTitle>
            <DialogDescription>
              {assignTarget && (
                <span>
                  {t('users.assignRoleTo', {
                    username: assignTarget.username,
                  })}
                </span>
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2 py-4">
            {allRoles
              .filter(
                (role) =>
                  !assignTarget?.roles?.some((r) => r.id === role.id),
              )
              .map((role) => (
                <Button
                  key={role.id}
                  variant="outline"
                  className="justify-between"
                  disabled={assignMutation.isLoading}
                  onClick={() =>
                    assignMutation.mutate({
                      userId: assignTarget.id,
                      roleId: role.id,
                    })
                  }
                >
                  <span>{role.name}</span>
                  <Badge variant="secondary">{role.key}</Badge>
                </Button>
              ))}
            {allRoles.length === 0 && (
              <p className="text-sm text-muted-foreground">
                {t('users.noAvailableRoles')}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setAssignTarget(null)}>
              {t('common.cancel')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}