class Cart < ApplicationRecord
  has_many :cart_items, dependent: :destroy

  validates :cart_id, presence: true, uniqueness: true
end