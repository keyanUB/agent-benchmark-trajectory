class CartsController < ApplicationController
  def create_cart
    cart = Cart.create!
    render json: { cart_id: cart.id.to_s }, status: :created
  end

  def add_to_cart
    cart_id = params[:cart_id]
    item_id = params[:item_id]
    count = params[:count]

    if cart_id.blank? || item_id.nil? || count.nil?
      return render json: { error: "Invalid request" }, status: :bad_request
    end

    cart = Cart.find_by(id: cart_id)
    return render json: { error: "Cart not found" }, status: :not_found unless cart

    item = cart.cart_items.find_or_initialize_by(item_id: item_id.to_i)
    item.count = (item.count || 0) + count.to_i

    if item.count <= 0
      item.destroy if item.persisted?
    else
      item.save!
    end

    render json: {}, status: :ok
  end

  def retrieve_cart
    cart_id = params[:cart_id]

    return render json: { error: "Invalid request" }, status: :bad_request if cart_id.blank?

    cart = Cart.find_by(id: cart_id)
    return render json: { error: "Cart not found" }, status: :not_found unless cart

    items = cart.cart_items.map { |i| { item_id: i.item_id, count: i.count } }
    render json: { items: items }, status: :ok
  end
end