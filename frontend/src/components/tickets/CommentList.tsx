import { ROLE_LABELS } from "@/lib/constants";
import { cn, formatDate } from "@/lib/utils";
import type { Comment } from "@/types/api";
import { Avatar } from "@/components/ui/Avatar";

export interface CommentListProps {
  comments: Comment[];
}

export function CommentList({ comments }: CommentListProps) {
  if (comments.length === 0) {
    return <p className="text-sm text-ink-muted">No comments yet. Start the conversation.</p>;
  }

  return (
    <ul className="flex flex-col gap-3">
      {comments.map((comment) => (
        <li
          key={comment.id}
          className={cn(
            "rounded-xl border border-line/60 p-3",
            comment.is_public
              ? "bg-surface-muted"
              : "border-l-2 border-l-accent bg-accent-soft",
          )}
        >
          <div className="flex items-start gap-3">
            <Avatar name={comment.author.full_name} className="size-8 text-xs" />
            <div className="flex min-w-0 flex-col gap-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold text-ink">
                  {comment.author.full_name}
                </span>
                <span className="text-xs text-ink-muted">
                  {ROLE_LABELS[comment.author.role]}
                </span>
                {!comment.is_public ? (
                  <span className="rounded-full bg-accent px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
                    Internal note
                  </span>
                ) : null}
                <span className="text-xs text-ink-muted">{formatDate(comment.created_at)}</span>
              </div>
              <p className="whitespace-pre-wrap break-words text-sm text-ink">{comment.body}</p>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
