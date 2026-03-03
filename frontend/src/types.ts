export type TaskStatus = 'todo' | 'in_progress' | 'blocked' | 'done' | 'cancelled';

export interface Task {
  id: number;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: number;
  due_at: string | null;
  location: string | null;
  assignee_name: string | null;
  source_platform: string;
  work_category: string | null;
  source_message_preview?: string | null;
  source_message_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface TaskDetails {
  task: Task;
  source_message_content: string | null;
  summary: string;
  todo_items: string[];
  stakeholders: string[];
}

export interface Contact {
  id: number;
  platform: string;
  platform_user_id: string;
  display_name: string;
  tags_json: {
    manual?: string[];
    ai?: string[];
    pending?: string[];
  };
  last_seen_at: string;
}

export interface CalendarEvent {
  id: string;
  source: string;
  title: string;
  start_at: string;
  end_at: string;
  location?: string | null;
}
