## Git and Version Control Policy

From now on, follow these rules for all development tasks:

1. **Never execute `git add`, `git commit`, `git push`, `git merge`, `git reset`, `git rebase`, or any other Git history-modifying command without my explicit approval.**
2. Never create, delete, rename, or switch Git branches without my permission.
3. Implement code changes directly in the working tree and leave them available for manual review in VS Code.
4. I am exclusively responsible for approving changes, creating commits, and pushing to GitHub.
5. You may execute read-only Git commands, such as `git status`, `git diff`, and `git log`, for inspection.
6. After completing a task, report all modified files, tests performed, and any automatically generated checkpoint commits.
7. Do not initiate GitHub synchronization or deployment unless explicitly requested.
8. Preserve the active branch `chore/main-branch-alignment`.

These rules apply to all future tasks in this project. Do not interpret approval to implement code as permission to commit it.

If Replit's internal checkpoint mechanism creates Git commits automatically, inform me. Do not attempt to remove or rewrite those checkpoints.