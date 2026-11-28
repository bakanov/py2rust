//! In-place min-heaps over the subset's totally ordered value types.

use crate::Result;

fn rise<T: Ord>(heap: &mut [T], start: usize, mut position: usize) {
    while position > start {
        let parent = (position - 1) / 2;
        if heap[position] >= heap[parent] {
            break;
        }
        heap.swap(position, parent);
        position = parent;
    }
}

fn repair<T: Ord>(heap: &mut [T], start: usize) {
    let mut position = start;
    // Descend along the smaller children, choosing the right on equal values,
    // then rise from the leaf. This also retains Python heapq's list layout.
    while position < heap.len() / 2 {
        let mut child = position * 2 + 1;
        if child + 1 < heap.len() && heap[child] >= heap[child + 1] {
            child += 1;
        }
        heap.swap(position, child);
        position = child;
    }
    rise(heap, start, position);
}

pub fn heapify<T: Ord>(heap: &mut [T]) {
    for position in (0..heap.len() / 2).rev() {
        repair(heap, position);
    }
}

pub fn heappush<T: Ord>(heap: &mut Vec<T>, item: T) {
    heap.push(item);
    let position = heap.len() - 1;
    rise(heap, 0, position);
}

pub fn heappop<T: Ord>(heap: &mut Vec<T>) -> Result<T> {
    let last = heap.pop().ok_or("index out of range")?;
    if heap.is_empty() {
        return Ok(last);
    }
    let first = std::mem::replace(&mut heap[0], last);
    repair(heap, 0);
    Ok(first)
}

pub fn heapreplace<T: Ord>(heap: &mut [T], item: T) -> Result<T> {
    let first = std::mem::replace(heap.first_mut().ok_or("index out of range")?, item);
    repair(heap, 0);
    Ok(first)
}

pub fn heappushpop<T: Ord>(heap: &mut [T], item: T) -> T {
    if !heap.is_empty() && heap[0] < item {
        let first = std::mem::replace(&mut heap[0], item);
        repair(heap, 0);
        first
    } else {
        item
    }
}
